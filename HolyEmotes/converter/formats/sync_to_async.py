from functools import partial
import asyncio


async def run_function_async(loop: asyncio.AbstractEventLoop, function, *args, **kwargs):
    function = partial(function, *args, **kwargs)
    return await loop.run_in_executor(None, function)
