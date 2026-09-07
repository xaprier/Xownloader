import asyncio
import json
import re
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from pydantic import HttpUrl

from xownloader_server.models import DownloadJob

ProgressCallback = Callable[[float], Awaitable[None]]


class ProviderAdapter(Protocol):
    name: str

    async def download(
        self,
        job: DownloadJob,
        output_directory: Path,
        progress_callback: ProgressCallback,
    ) -> list[Path]:
        """Download a job and return the published file paths, primary first."""

    async def inspect(self, source_url: HttpUrl) -> dict[str, object]:
        """Return provider metadata without downloading media."""


class YtDlpAdapter:
    name = "youtube"

    async def inspect(self, source_url: HttpUrl) -> dict[str, object]:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "yt_dlp",
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            "--no-warnings",
            str(source_url),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            message = stderr.decode(errors="replace").strip()[-1000:]
            raise RuntimeError(message or "yt-dlp metadata inspection failed")
        raw = json.loads(stdout)
        duration = raw.get("duration")
        return {
            "provider": "youtube",
            "title": str(raw.get("title") or "Untitled media"),
            "uploader": raw.get("uploader") or raw.get("channel"),
            "thumbnail": raw.get("thumbnail"),
            "duration_seconds": int(duration) if isinstance(duration, (int, float)) else None,
            "media_items": None,
        }

    async def download(
        self,
        job: DownloadJob,
        output_directory: Path,
        progress_callback: ProgressCallback,
    ) -> list[Path]:
        output_directory.mkdir(parents=True, exist_ok=True)
        output_template = output_directory / f"{job.id}.%(ext)s"
        command = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--restrict-filenames",
            "--write-info-json",
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
        stderr_task = asyncio.create_task(process.stderr.read())
        try:
            while line := await process.stdout.readline():
                match = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", line.decode())
                if match:
                    await progress_callback(float(match.group(1)))
            await process.wait()
            stderr = await stderr_task
        except asyncio.CancelledError:
            process.terminate()
            await process.wait()
            stderr_task.cancel()
            raise
        if process.returncode != 0:
            message = stderr.decode(errors="replace").strip()[-1000:]
            raise RuntimeError(message or "yt-dlp failed")

        candidates = sorted(
            path
            for path in output_directory.glob(f"{job.id}.*")
            if not path.name.endswith(".info.json")
        )
        if not candidates:
            raise RuntimeError("yt-dlp completed without producing an output file")
        return [candidates[0]]
