# encoder — builds ffmpeg commands and runs them, reports progress back to the UI

import subprocess
import re
import os
import tempfile
import shutil
from pathlib import Path
from threading import Thread
from typing import Callable, Optional
from codimux.probe import ProbeResult, probe


ProgressCallback = Callable[[int, int, float, float], None]
DoneCallback = Callable[[bool, str], None]  # success, message
LogCallback = Callable[[str], None]


def _estimate_total_frames(filepath: str, probe_result: ProbeResult) -> int:
    # estimate total frames so we can show a progress percentage
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", filepath],
            capture_output=True, text=True, timeout=30
        )
        duration = float(result.stdout.strip())
        fps_str = probe_result.video.fps if probe_result.video else "24/1"
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
        return int(duration * fps)
    except Exception:
        return 0


def _parse_progress(line: str):
    # pull frame count and speed out of ffmpeg's stats output
    frame = None
    speed = None
    fm = re.search(r"frame=\s*(\d+)", line)
    sm = re.search(r"speed=\s*([\d.]+)x", line)
    if fm:
        frame = int(fm.group(1))
    if sm:
        speed = float(sm.group(1))
    return frame, speed


def build_ffmpeg_cmd(
    input_path: str,
    output_path: str,
    preset: dict,
    audio_indices: list[int],
    sub_indices: list[int],
    hardsub_tmp: Optional[str],
    video_action: str,
    audio_actions: list[str],
    hardsub_index: Optional[int] = None,  # set for PGS overlay path
) -> list[str]:
    # PGS overlay uses filter_complex, not -vf, so handle separately
    use_pgs_overlay = hardsub_index is not None and hardsub_tmp is None

    if use_pgs_overlay:
        # PGS: input + filter_complex overlay
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats",
            "-probesize", "100M", "-analyzeduration", "100M",
            "-i", input_path,
        ]
        w, h = preset["width"], preset["height"]
        scale = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
        )
        filter_complex = (
            f"[0:v][0:s:{hardsub_index}]overlay,{scale}[vout]"
        )
        cmd += ["-filter_complex", filter_complex, "-map", "[vout]"]
    else:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-stats",
            "-probesize", "100M", "-analyzeduration", "100M",
            "-i", input_path,
            "-map", "0:v:0",
        ]

    # Audio maps
    for idx in audio_indices:
        cmd += ["-map", f"0:a:{idx}"]

    # Soft subtitle maps
    for idx in sub_indices:
        cmd += ["-map", f"0:s:{idx}"]

    # Video codec args
    if not use_pgs_overlay:
        if video_action == "copy":
            cmd += ["-c:v", "copy"]
            vf = None
        else:
            codec = preset["video_codec"]
            cmd += [
                "-c:v", codec,
                "-crf", str(preset["crf"]),
                "-preset", preset.get("preset", "medium"),
                "-maxrate", preset["max_bitrate"],
                "-bufsize", preset["bufsize"],
            ]
            if codec == "libx265":
                cmd += ["-tag:v", "hvc1"]
            if codec == "libx264":
                if "h264_profile" in preset:
                    cmd += ["-profile:v", preset["h264_profile"]]
                if "h264_level" in preset:
                    cmd += ["-level:v", preset["h264_level"]]
            w, h = preset["width"], preset["height"]
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
            )

        # Text-based hardsub vf injection
        if hardsub_tmp:
            escaped = hardsub_tmp.replace("\\", "\\\\").replace(":", "\\:")
            sub_vf = f"subtitles='{escaped}'"
            if vf:
                vf = f"{sub_vf},{vf}"
            else:
                vf = f"{sub_vf},format=yuv420p"

        if vf:
            cmd += ["-vf", vf]
    else:
        # PGS path — still need video codec args after filter_complex
        codec = preset["video_codec"]
        cmd += [
            "-c:v", codec,
            "-crf", str(preset["crf"]),
            "-preset", preset.get("preset", "medium"),
            "-maxrate", preset["max_bitrate"],
            "-bufsize", preset["bufsize"],
        ]
        if codec == "libx265":
            cmd += ["-tag:v", "hvc1"]
        if codec == "libx264":
            if "h264_profile" in preset:
                cmd += ["-profile:v", preset["h264_profile"]]
            if "h264_level" in preset:
                cmd += ["-level:v", preset["h264_level"]]

    # Force fps if preset requires it
    if "force_fps" in preset and video_action == "encode":
        cmd += ["-r", str(preset["force_fps"])]

    # Per-track audio codec
    for i, (idx, action) in enumerate(zip(audio_indices, audio_actions)):
        if action == "copy":
            cmd += [f"-c:a:{i}", "copy"]
        else:
            acodec = preset["audio_codec"]
            if acodec == "libopus":
                # Opus requires explicit stereo downmix before encoding —
                # use pan filter to safely handle any channel layout including 5.1(side)
                cmd += [
                    f"-filter:a:{i}", "pan=stereo|FL=0.5*FC+0.707*FL+0.707*BL+0.5*LFE|FR=0.5*FC+0.707*FR+0.707*BR+0.5*LFE",
                    f"-c:a:{i}", acodec,
                    f"-b:a:{i}", preset["audio_bitrate"],
                    f"-ar:{i}", str(preset["audio_samplerate"]),
                ]
            else:
                cmd += [
                    f"-c:a:{i}", acodec,
                    f"-b:a:{i}", preset["audio_bitrate"],
                    f"-ar:{i}", str(preset["audio_samplerate"]),
                    f"-ac:{i}", "2",
                ]

    # Subtitle copy
    if sub_indices:
        cmd += ["-c:s", "copy"]

    cmd += ["-map_metadata", "-1", "-movflags", "+faststart", output_path]
    return cmd


class EncodeJob:
    # one encode job per file

    def __init__(
        self,
        input_path: str,
        output_path: str,
        preset: dict,
        audio_indices: list[int],
        sub_indices: list[int],
        hardsub_index: Optional[int],
        video_action: str,
        audio_actions: list[str],
        probe_result: ProbeResult,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.preset = preset
        self.audio_indices = audio_indices
        self.sub_indices = sub_indices
        self.hardsub_index = hardsub_index
        self.video_action = video_action
        self.audio_actions = audio_actions
        self.probe_result = probe_result
        self.total_frames = 0  # calculated in thread
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process:
            self._process.terminate()

    def run(self, on_progress: ProgressCallback, on_done: DoneCallback, on_log=None):
        Thread(target=self._run_thread, args=(on_progress, on_done, on_log), daemon=True).start()

    def _run_thread(self, on_progress: ProgressCallback, on_done: DoneCallback, on_log=None):
        print(f"[CoDiMux] _run_thread started for: {self.input_path}")
        self.total_frames = _estimate_total_frames(self.input_path, self.probe_result)
        tmp_dir = None
        hardsub_tmp = None

        try:
            # Determine if hardsub track is text-based or image-based (PGS)
            hardsub_is_pgs = False
            if self.hardsub_index is not None:
                hardsub_track = next(
                    (s for s in self.probe_result.subtitles
                     if s.index == self.hardsub_index), None
                )
                hardsub_is_pgs = (
                    hardsub_track is not None and not hardsub_track.is_text_based()
                )

            # Text-based hardsub — extract to temp file to avoid double-probe hang
            if self.hardsub_index is not None and not hardsub_is_pgs:
                tmp_dir = tempfile.mkdtemp(prefix="codimux_")
                hardsub_tmp = os.path.join(tmp_dir, "sub.ass")
                extract_result = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-probesize", "100M", "-analyzeduration", "100M",
                        "-i", self.input_path,
                        "-map", f"0:s:{self.hardsub_index}",
                        hardsub_tmp,
                    ],
                    capture_output=True, text=True, timeout=300,
                )
                if not os.path.exists(hardsub_tmp):
                    on_done(False, f"Failed to extract subtitle: {extract_result.stderr}")
                    return

            # Must re-encode video to burn subs in
            if self.hardsub_index is not None and self.video_action == "copy":
                self.video_action = "encode"

            # Build soft sub list (exclude hardsub track)
            soft_subs = [i for i in self.sub_indices if i != self.hardsub_index]

            cmd = build_ffmpeg_cmd(
                input_path=self.input_path,
                output_path=self.output_path,
                preset=self.preset,
                audio_indices=self.audio_indices,
                sub_indices=soft_subs,
                hardsub_tmp=hardsub_tmp,
                hardsub_index=self.hardsub_index if hardsub_is_pgs else None,
                video_action=self.video_action,
                audio_actions=self.audio_actions,
            )

            print(f"[CoDiMux] ffmpeg cmd: {' '.join(cmd)}")
            self._process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            for line in self._process.stderr:
                if self._cancelled:
                    break
                line = line.rstrip()
                if on_log and line:
                    on_log(line)
                frame, speed = _parse_progress(line)
                if frame is not None:
                    eta = 0.0
                    if speed and speed > 0 and self.total_frames > 0:
                        remaining_frames = self.total_frames - frame
                        # speed is Nx realtime; at 24fps source, 1x = 24fps encode
                        src_fps_str = self.probe_result.video.fps if self.probe_result.video else "24/1"
                        try:
                            num, den = src_fps_str.split("/")
                            src_fps = float(num) / float(den)
                        except Exception:
                            src_fps = 24.0
                        encode_fps = speed * src_fps
                        eta = remaining_frames / encode_fps if encode_fps > 0 else 0
                    on_progress(frame, self.total_frames, speed or 0.0, eta)

            self._process.wait()

            if self._cancelled:
                Path(self.output_path).unlink(missing_ok=True)
                on_done(False, "Cancelled")
            elif self._process.returncode == 0:
                on_done(True, "Done")
            else:
                Path(self.output_path).unlink(missing_ok=True)
                on_done(False, f"ffmpeg exited with code {self._process.returncode}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[CoDiMux] Exception in encoder: {e}")
            Path(self.output_path).unlink(missing_ok=True)
            on_done(False, str(e))
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
