import asyncio
import glob
from typing import Literal
from tempfile import TemporaryDirectory

import magic
from PIL import Image, ImageSequence

from formats import FORMATS, Any

MAX_SIZE_STICKER = 200 * 1024
MAX_SIZE_EMOJI = 60 * 1024
MAX_DURATION = 3.00
MAX_FPS = 30


class Converter:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        file: str,
        sticker_type: Literal["regular", "custom_emoji"],
    ) -> None:
        self._file = file
        self._sticker_type = sticker_type
        if self._sticker_type == "regular":
            self._max_size = MAX_SIZE_STICKER
        else:
            self._max_size = MAX_SIZE_EMOJI
        self._loop = loop

    async def convert(self):
        with TemporaryDirectory() as tmpdir:
            print(tmpdir)
            mime = magic.from_file(self._file, True).lower()
            print(mime)
            format = FORMATS.get(mime, Any)(self._loop, self._file, tmpdir)
            print("extract_frames")
            one_frame, total_frames = await format.extract_frames()
            print("after extract_frames", one_frame, total_frames)
            if not total_frames or total_frames == 1:
                await format.close()
                return await self.convert_to_webp(), "webp"
            fps = min(1000 // one_frame, 30)
            duration = total_frames / fps
            speed_up = None
            if duration >= MAX_DURATION:
                speed_up = round((duration / (MAX_DURATION)), 5)
            return await self.render(fps, tmpdir, speed_up), "webm"
            return
            if "gif" in mime:
                durations = self.get_gif_durations()
                if not durations or len(durations) == 1:
                    return await self.convert_to_webp(), "webp"
            elif "webp" in mime:
                durations = await self.get_webp_durations()
                if not durations or len(durations) == 1:
                    return await self.convert_to_webp(), "webp"
            elif "avif" in mime:
                durations = self.get_avif_durations()
                if not durations or len(durations) == 1:
                    return await self.convert_to_webp(), "webp"
            else:
                return await self.convert_to_webp(), "webp"
            print(durations)
            fps = min(1000 / min(durations), 30)
            all_frames = self.get_frames(durations, tmpdir)
            duration = all_frames / fps
            speed_up = None
            if duration >= MAX_DURATION:
                speed_up = round((duration / (MAX_DURATION)), 5)
            return await self.render(fps, tmpdir, speed_up), "webm"

    async def convert_to_webp(self) -> bytes:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            self._file,
            "-f",
            "webp",
            "-c:v",
            "libwebp",
            "-vf",
            "scale=512:-2" if self._sticker_type == "regular" else "scale=100:100",
            "-",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.DEVNULL,
        )
        converted, _ = await proc.communicate()
        return converted

    def get_frames(self, durations: list[int], tmpdir: str) -> int:
        minimum = min(durations)
        image = Image.open(self._file)
        sequence = ImageSequence.Iterator(image)
        index = 0
        for i in range(len(durations)):
            frame = sequence[i]
            for _ in range(durations[i] // minimum):
                frame.save(f"{tmpdir}/{str(index).zfill(8)}.png")
                index += 1
        return len(glob.glob(f"{tmpdir}/*"))

    async def render(
        self,
        fps: int,
        tmpdir: str,
        speed_up: float = None,
    ) -> bytes:
        target_fps = min(round(fps * speed_up), MAX_FPS)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            f"{tmpdir}/%08d.png",
            "-f",
            "lavfi",
            "-i",
            "color=c=white@0.0,format=rgba",
            "-shortest",
            "-filter_complex",
            (
                "[0:v]"
                + (
                    "scale='if(gt(iw,ih),512,-1)':'(if(gt(ih,iw),512,-1))'"
                    if self._sticker_type == "regular"
                    else "scale=100:100"
                )
                + "[scaled];"
                + (
                    f"[scaled]fps={target_fps}, setpts=(1/{speed_up})*PTS[speedup];[speedup]"
                    if speed_up
                    else "[scaled]"
                )
                + "[1:v]overlay=shortest=1,format=yuva420p[out]"
            ),
            "-map",
            "[out]",
            "-c:v",
            "libvpx-vp9",
            "-f",
            "webm",
            "-pix_fmt",
            "yuva420p",
            "-crf",
            "17",
            "-b:v",
            "50K" if self._sticker_type == "regular" else "20K",
            "-maxrate",
            "50K" if self._sticker_type == "regular" else "20K",
            "-bufsize",
            "50K" if self._sticker_type == "regular" else "20K",
            "pipe:",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.DEVNULL,
        )
        content, _ = await process.communicate()
        return content


if __name__ == "__main__":

    def extract_id(url: str):
        if "jtvnw.net" in url:
            return url.split("/emoticons/v2/")[-1].split("/")[0]
        else:
            return url.split("emote/")[-1].split("/")[0]

    async def main():
        loop = asyncio.get_event_loop()
        conv = Converter(
            loop, "/home/user/projects/7tvtotelegram/wicked.webp", "regular"
        )
        content, ext = await conv.convert()
        with open(f"test.{ext}", "wb") as f:
            f.write(content)

    asyncio.run(main())
