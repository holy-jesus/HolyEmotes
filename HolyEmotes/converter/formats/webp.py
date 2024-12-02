import asyncio

from PIL import Image

from .utils import run_function_async, durations_to_frames


class WEBP:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, file_path: str, tmpdir: str
    ) -> None:
        self._loop = loop
        self._file_path = file_path
        self._tmpdir = tmpdir
        self._image = Image.open(file_path)

    async def extract_frames(self) -> tuple[int, int]:
        process = await asyncio.create_subprocess_exec(
            "webpmux",
            "-info",
            self._file_path,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        durations = []
        start = False
        duration_index = -1
        for line in stdout.decode().splitlines():
            if "duration" in line:
                duration_index = line.split().index("duration")
                start = True
                continue
            if not start:
                continue
            try:
                durations.append(int(line.split()[duration_index]))
            except IndexError:
                pass
        gcd, frames = durations_to_frames(durations)
        return gcd, await run_function_async(self._loop, self.__extract_frames, frames)

    async def close(self):
        return await run_function_async(self._loop, self.__close)

    def __extract_frames(self, frames: dict[int, int]) -> int:
        file_index = 0
        for frame_index, repeat in frames.items():
            self._image.seek(frame_index)
            for _ in range(repeat):
                self._image.save(f"{self._tmpdir}/{file_index:08d}.png")
        return file_index

    def __close(self):
        self._image.close()
