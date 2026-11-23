# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import asyncio
import json
import os


async def probe_codec(path: str) -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name", "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(out.decode())
        streams = data.get("streams") or []
        return streams[0].get("codec_name") if streams else None
    except Exception:
        return None


async def probe_video_meta(path: str) -> tuple[int, int, int]:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return 0, 0, 0
    try:
        data = json.loads(out.decode())
        streams = data.get("streams") or []
        if not streams:
            return 0, 0, 0
        stream = streams[0]
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        duration = int(float(stream.get("duration") or 0))
        return width, height, duration
    except Exception:
        return 0, 0, 0


async def ensure_audio(input_path: str) -> tuple[str, str]:
    codec = await probe_codec(input_path)
    if codec == "mp3":
        return input_path, os.path.splitext(input_path)[1] or ".mp3"

    base, _ = os.path.splitext(input_path)

    if codec == "opus":
        output_path = f"{base}.arcconv.ogg"
        args = ["-y", "-i", input_path, "-vn", "-c:a", "copy", output_path]
    else:
        output_path = f"{base}.arcconv.mp3"
        args = ["-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-b:a", "192k", output_path]

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg conversion failed: {stderr.decode()[-500:]}")

    return output_path, os.path.splitext(output_path)[1]


async def _run_ffmpeg(args: list[str], timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-nostdin", "-loglevel", "error", *args,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"Stream download timed out after {int(timeout)}s")
    return proc.returncode, stderr.decode(errors="replace")[-500:]


async def download_hls(
    url: str, output_path: str, *, user_agent: str, timeout: float = 1800.0, max_bytes: int | None = None,
) -> str:
    base = ["-y", "-user_agent", user_agent, "-f", "hls", "-i", url, "-c", "copy", "-movflags", "+faststart"]
    if max_bytes:
        base += ["-fs", str(max_bytes)]

    last_err = ""
    for extra in (["-bsf:a", "aac_adtstoasc"], []):
        code, last_err = await _run_ffmpeg([*base, *extra, output_path], timeout)
        if code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        if os.path.exists(output_path):
            os.remove(output_path)

    raise RuntimeError(f"Couldn't download the stream: {last_err.strip() or 'ffmpeg failed'}")
