import asyncio

from PIL import Image

from .utils import run_function_async, durations_to_frames


class GIF:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, file_path: str, tmpdir: str
    ) -> None:
        self._loop = loop
        self._tmpdir = tmpdir
        self._image = Image.open(file_path)

    async def extract_frames(self) -> tuple[int, int]:
        return await run_function_async(self._loop, self.__extract_frames)

    async def close(self) -> None:
        return await run_function_async(self._loop, self.__close)

    def __extract_frames(self) -> tuple[int, int]:
        durations = self.__get_durations()
        gcd, frames = durations_to_frames(durations)
        file_index = 0
        for frame_index, repeat in frames.items():
            self._image.seek(frame_index)
            for _ in range(repeat):
                self._image.save(f"{self._tmpdir}/{file_index:08d}.png")
                file_index += 1
        return gcd, file_index

    def __get_durations(self) -> list[int]:
        durations = []
        i = 0
        while True:
            try:
                self._image.seek(i)
                durations.append(self._image.info["duration"])
                i += 1
            except EOFError:
                break
        return durations

    def __close(self):
        self._image.close()
