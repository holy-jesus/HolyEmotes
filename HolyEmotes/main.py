import traceback

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response, PlainTextResponse
from aiogram.types.update import Update

from bot import SECRET, startup, shutdown, bot, dp


async def lifespan(app: FastAPI):
    await startup()
    yield
    await shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/page")
async def page(request: Request):
    return PlainTextResponse("ТЕСТ")


@app.post("/webhook")
async def webhook(request: Request):
    assert request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") == SECRET
    update = Update.model_validate(await request.json(), context={"bot": bot})
    try:
        await dp.feed_update(bot, update)
    except Exception:
        print(traceback.format_exc())
    return Response()


@app.get("/")
async def index():
    return RedirectResponse("https://t.me/HolyStickersBot", status_code=301)
