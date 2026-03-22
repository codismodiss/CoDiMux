# ffprobe wrapper — reads stream info from video files

import subprocess
import json
from dataclasses import dataclass, field
from typing import Optional


def _escape(text: str) -> str:
    # GTK labels interpret & < > as markup so escape them
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class VideoStream:
    index: int
    codec: str
    width: int
    height: int
    fps: str


@dataclass
class AudioStream:
    index: int
    codec: str
    language: str
    title: str
    channels: int
    sample_rate: int

    def display(self) -> str:
        lang = _escape(self.language or "und")
        title = _escape(self.title or "(no title)")
        return f"#{self.index} — {self.codec} — {lang} — {title}"


@dataclass
class SubtitleStream:
    index: int
    codec: str
    language: str
    title: str

    def is_text_based(self) -> bool:
        return self.codec in ("ass", "ssa", "subrip", "srt", "webvtt", "mov_text")

    def display(self) -> str:
        lang = _escape(self.language or "und")
        title = _escape(self.title or "(no title)")
        return f"#{self.index} — {self.codec} — {lang} — {title}"


@dataclass
class ProbeResult:
    video: Optional[VideoStream] = None
    audio: list[AudioStream] = field(default_factory=list)
    subtitles: list[SubtitleStream] = field(default_factory=list)
    error: Optional[str] = None


def probe(filepath: str) -> ProbeResult:
    """Run ffprobe on a file and return structured stream info."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-probesize", "100M",
                "-analyzeduration", "100M",
                "-show_streams",
                "-print_format", "json",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return ProbeResult(error="ffprobe timed out")
    except Exception as e:
        return ProbeResult(error=str(e))

    probe_result = ProbeResult()
    audio_idx = 0
    sub_idx = 0

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        tags = stream.get("tags", {})
        lang = tags.get("language", "") or tags.get("LANGUAGE", "")
        title = tags.get("title", "") or tags.get("TITLE", "")
        abs_index = stream.get("index", 0)

        if codec_type == "video" and probe_result.video is None:
            probe_result.video = VideoStream(
                index=abs_index,
                codec=stream.get("codec_name", "unknown"),
                width=stream.get("width", 0),
                height=stream.get("height", 0),
                fps=stream.get("r_frame_rate", "unknown"),
            )

        elif codec_type == "audio":
            probe_result.audio.append(AudioStream(
                index=audio_idx,
                codec=stream.get("codec_name", "unknown"),
                language=lang,
                title=title,
                channels=stream.get("channels", 2),
                sample_rate=int(stream.get("sample_rate", 48000)),
            ))
            audio_idx += 1

        elif codec_type == "subtitle":
            probe_result.subtitles.append(SubtitleStream(
                index=sub_idx,
                codec=stream.get("codec_name", "unknown"),
                language=lang,
                title=title,
            ))
            sub_idx += 1

    return probe_result
