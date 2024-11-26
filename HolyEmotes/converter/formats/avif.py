import asyncio

import av
from av.video.stream import VideoStream

from .sync_to_async import run_function_async
from .durations_to_frames import durations_to_frames


class AVIF:
    def __init__(
        self, loop: asyncio.AbstractEventLoop, file_path: str, tmpdir: str
    ) -> None:
        self._loop = loop
        self._tmpdir = tmpdir
        self._container = av.open(file_path)
        self._stream_index = self._select_video_stream()

    async def extract_frames(self) -> tuple[int, int]:
        return await run_function_async(self._loop, self.__extract_frames)

    async def close(self) -> None:
        return await run_function_async(self._loop, self.__close)

    def __close(self) -> None:
        self._container.close()

    def __extract_frames(self) -> tuple[int, int]:
        durations = self.__get_durations()
        gcd, frames = durations_to_frames(durations)
        file_index = 0
        self._container.seek(0)
        for frame, repeat in zip(
            self._container.decode(video=self._stream_index),
            frames.values(),
        ):
            for _ in range(repeat):
                frame.to_image().save(f"{self._tmpdir}/{file_index:08d}.png")
                file_index += 1
        return gcd, file_index

    def __get_durations(self) -> list[int]:
        durations = []
        prev_duration = 0
        self._container.seek(0)
        for i, frame in enumerate(self._container.decode(video=self._stream_index)):
            ms_duration = frame.pts * 10
            if i == 0:
                continue
            durations.append(ms_duration - prev_duration)
            prev_duration = ms_duration
        if self._container.duration:
            durations.append(round(self._container.duration / 1000) - ms_duration)
        return durations

    def _select_video_stream(self) -> int:
        for i, video in enumerate(self._container.streams.video):
            if video.pix_fmt == "gray" or video.metadata.get("title", None) == "Alpha":
                continue
            if len(self._container.streams.video) == 2:
                return i
            elif len(self._container.streams.video) == 4 and video.frames > 1:
                return i
        return self._container.streams.video.index(
            self._container.streams.best("video")
        )
