import math


def durations_to_frames(durations: list[int]) -> tuple[int, dict[int, int]]:
    gcd = math.gcd(*durations)
    frames = {}
    for i, duration in enumerate(durations):
        frames[i] = duration // gcd
    return gcd, frames
