import asyncio
import os
from typing import Literal
import glob

import magic
from PIL import Image, ImageSequence

MAX_SIZE = 200 * 1024
MAX_DURATION = 3.00


class Converter:
    async def convert(self, file: str, sticker_type: Literal["regular", "custom_emoji"]):
        os.system("rm -rf /tmp/frames/")
        os.system("mkdir /tmp/frames/")
        mime = magic.from_file(file, True).lower()
        if "gif" in mime:
            durations = self.get_gif_durations(file)
            if not durations:
                return await self.convert_to_webp(file, sticker_type), "webp"
        elif "webp" in mime:
            durations = await self.get_webp_durations(file)
            if not durations:
                return await self.convert_to_webp(file, sticker_type), "webp"
        else:
            return await self.convert_to_webp(file, sticker_type), "webp"
        fps = min(1000 / min(durations), 30)
        all_frames = self.get_frames(file, durations)
        duration = all_frames / fps
        speed_up = None
        if duration >= MAX_DURATION:
            speed_up = round((duration / (MAX_DURATION - 0.1)), 5)
        return await self.render(fps, sticker_type, speed_up), "webm"

    async def get_webp_durations(self, file: str) -> list[int]:
        process = await asyncio.create_subprocess_exec(
            "./libwebp/bin/webpmux", "-info", file, stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        durations = []
        start = False
        for line in stdout.decode().splitlines():
            if "duration" in line:
                start = True
                continue
            if not start:
                continue
            try:
                durations.append(int(line.split()[6]))
            except IndexError:
                pass
        return durations

    def get_gif_durations(self, file: str):
        durations = []
        img = Image.open(file)
        i = 0
        while True:
            try:
                img.seek(i)
                durations.append(img.info["duration"])
                i += 1
            except EOFError:
                break
        return durations

    async def convert_to_webp(self, file: str, sticker_type: str) -> bytes:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            file,
            "-f",
            "webp",
            "-c:v",
            "libwebp",
            "-vf",
            "scale=512:-2" if sticker_type == "regular" else "scale=100:100",
            "-",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.DEVNULL,
        )
        converted, _ = await proc.communicate()
        return converted

    def get_frames(self, file: str, durations: list[int]) -> int:
        minimum = min(durations)
        image = Image.open(file)
        sequence = ImageSequence.Iterator(image)
        index = 0
        for i in range(len(durations)):
            frame = sequence[i]
            for _ in range(durations[i] // minimum):
                frame.save(f"/tmp/frames/{str(index).zfill(8)}.png")
                index += 1
        return len(glob.glob("/tmp/frames/*"))

    async def render(
        self, fps: int, sticker_type: Literal["regular", "custom_emoji"], speed_up: float = None
    ) -> bytes:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            "/tmp/frames/%08d.png",
            "-f",
            "lavfi",
            "-i",
            "color=c=white@0.0,format=rgba",
            "-shortest",
            "-filter_complex",
            (
                "[0:v]"
                + ("scale=512:-2" if sticker_type == "regular" else "scale=100:100")
                + "[scaled];"
                + (
                    f"[scaled]fps={str(fps)}, setpts=(1/{speed_up})*PTS[speedup];[speedup]"
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
            # "-crf",
            # "50",
            "-pix_fmt",
            "yuva420p",
            # "-preset", "slow",
            "-b:v",
            "50K",
            "pipe:",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.DEVNULL,
        )
        content, _ = await process.communicate()
        os.system("rm -rf /tmp/frames/")
        return content


if __name__ == "__main__":
    import aiohttp

    def extract_id(url: str):
        if "jtvnw.net" in url:
            return url.split("/emoticons/v2/")[-1].split("/")[0]
        else:
            return url.split("emote/")[-1].split("/")[0]

    async def main():
        conv = Converter()
        content, ext = await conv.convert(
            "/home/user/booba2/wicked.webp", "custom_emoji"
        )
        with open("test.webm", "wb") as f:
            f.write(content)
        # session = aiohttp.ClientSession()
        # converter = Converter()

        # response = await session.get(
        #     "https://emotes.adamcy.pl/v1/channel/olesha/emotes/all"
        # )
        # emojis = await response.json()

        # for emoji in emojis[:30]:
        #     url = emoji["urls"][-1]["url"]
        #     response = await session.get(url)
        #     content = await response.read()
        #     with open("/tmp/emoji", "wb") as f:
        #         f.write(content)
        #     content, ext = await converter.convert("/tmp/emoji", "custom_emoji")
        #     with open("./emotes/" + extract_id(url) + f".{ext}", "wb") as f:
        #         f.write(content)

        # await session.close()

    asyncio.run(main())
