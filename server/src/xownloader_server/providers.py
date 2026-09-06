import asyncio
import sys
from pathlib import Path
from typing import Protocol

from xownloader_server.models import DownloadJob


class ProviderAdapter(Protocol):
    name: str

    async def download(self, job: DownloadJob, output_directory: Path) -> Path:
        """Download a job and return the published file path."""


class YtDlpAdapter:
    name = "youtube"

    async def download(self, job: DownloadJob, output_directory: Path) -> Path:
        output_directory.mkdir(parents=True, exist_ok=True)
        output_template = output_directory / f"{job.id}.%(ext)s"
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--restrict-filenames",
            "--newline",
            "--output",
            str(output_template),
        ]
        if job.output_format.value == "mp3":
            command.extend(["--extract-audio", "--audio-format", "mp3"])
            if job.audio_bitrate:
                command.extend(["--audio-quality", job.audio_bitrate])
        else:
            command.extend(["--format", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"])
            if job.video_quality:
                height = job.video_quality.removesuffix("p")
                command[command.index("bestvideo+bestaudio/best")] = (
                    f"bestvideo[height<={height}]+bestaudio/best"
                )
        command.append(str(job.source_url))

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode(errors="replace").strip()[-1000:]
            raise RuntimeError(message or "yt-dlp failed")

        candidates = sorted(output_directory.glob(f"{job.id}.*"))
        if not candidates:
            raise RuntimeError("yt-dlp completed without producing an output file")
        return candidates[0]