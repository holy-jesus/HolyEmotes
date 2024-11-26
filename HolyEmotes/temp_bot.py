import asyncio
import os
import math
from time import time
from typing import Literal
from uuid import uuid4
import json

import aiohttp
import emoji
import emoji.tokenizer
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    BufferedInputFile,
    InputSticker,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    WebAppInfo,
    InlineQuery,
    InlineQueryResultCachedSticker,
)
from aiogram.fsm.storage.mongo import MongoStorage
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from convert import Converter

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB = os.getenv("MONGODB")
WEBHOOK = os.getenv("WEBHOOK")
SECRET = os.getenv("SECRET")

client = AsyncIOMotorClient(MONGODB)
db = client.HolyStickers
converter = Converter()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MongoStorage(client, db_name="HolyStickers"))
session: aiohttp.ClientSession = None
bot_account: User = None


class NewStickerSet(StatesGroup):
    pass


def extract_id(url: str):
    if "jtvnw.net" in url:
        return url.split("/emoticons/v2/")[-1].split("/")[0]
    else:
        return url.split("emote/")[-1].split("/")[0]


async def download_sticker(url: str, sticker_type: Literal["regular", "custom_emoji"]):
    response = await session.get(url)
    content = await response.read()
    with open("/tmp/emoji", "wb") as f:
        f.write(content)
    return await converter.convert("/tmp/emoji", sticker_type)


async def upload_sticker(
    sticker: dict,
    user_id: str,
    sticker_type: Literal["regular", "custom_emoji"],
    force: bool = False,
):
    url = sticker["urls"][-1]["url"]
    sticker_id = extract_id(url)
    sticker_document = await db.stickers.find_one(
        {"sticker_id": sticker_id, "sticker_type": sticker_type}
    )
    if force or not sticker_document:
        if force and sticker_document:
            await db.stickers.delete_one({"_id": sticker_document["_id"]})
        content, ext = await download_sticker(url, sticker_type)
        with open(f"/tmp/{sticker_id}.{ext}", "wb") as f:
            f.write(content)
        format = "video" if ext == "webm" else "static"
        file = await bot.upload_sticker_file(
            user_id,
            BufferedInputFile(
                content,
                filename=f"{sticker_id}.{ext}",
            ),
            format,
        )

        sticker_document = {
            "sticker_type": sticker_type,
            "sticker_id": sticker_id,
            "file_id": file.file_id,
            "file_unique_id": file.file_unique_id,
            "filename": f"{sticker_id}.{ext}",
            "format": format,
        }

        await db.stickers.insert_one(sticker_document)
    return InputSticker(
        sticker=sticker_document["file_id"],
        format=sticker_document["format"],
        emoji_list=["🪱"],
        keywords=[sticker["code"]],
    )


async def add_sticker_to_set(
    sticker: dict,
    user_id: int,
    set_name: str,
    sticker_type: Literal["regular", "custom_emoji"],
):
    await bot.add_sticker_to_set(
        user_id, set_name, await upload_sticker(sticker, user_id, sticker_type)
    )


async def get_sticker_list(channel: str):
    cached = await db.cache.find_one({"_id": channel})
    if cached and time() < cached["expires"]:
        return cached["stickers"]
    response = await session.get(
        f"https://emotes.adamcy.pl/v1/channel/{channel}/emotes/all"
    )
    stickers: list[dict] = await response.json()
    if "error" in stickers:
        return "Такого канала нету."
    elif len(stickers) == 0:
        return "На этом канале нету смайликов."
    document = {"_id": channel, "expires": time() + 3600, "stickers": stickers}
    await db.cache.update_one({"_id": channel}, {"$set": document}, True)
    return stickers


async def create_sticker_set(
    message: Message,
    state: MongoStorage,
    sticker_type: Literal["regular", "custom_emoji"],
):
    MAX_AMOUNT = {"regular": 120, "custom_emoji": 200}[sticker_type]
    args = message.text.split()

    if len(args) != 2:
        return

    sticker_set = await db.sticker_sets.find_one(
        {"owner_id": message.from_user.id, "channel": args[1]}
    )
    if sticker_set:
        return

    sticker_list = await get_sticker_list(args[1])
    if isinstance(sticker_list, str):
        return await message.answer(sticker_list)

    amount_of_sets = math.ceil(len(sticker_list) / MAX_AMOUNT)
    await message.answer(f"{amount_of_sets}")
    name = f"{args[1]}_{sticker_type}_by_{bot_account.username}"
    await bot.create_new_sticker_set(
        bot_account.id,
        name,
        f"Twitch {args[1]} by @{bot_account.username}",
        stickers=[
            await upload_sticker(sticker_list[0], message.from_user.id, sticker_type)
        ],
        sticker_type=sticker_type,
    )
    for sticker in sticker_list[1:5]:
        await add_sticker_to_set(sticker, message.from_user.id, name, sticker_type)


async def startup():
    global session, bot_account
    bot_account = await bot.get_me()
    assert await bot.set_webhook(
        WEBHOOK,
        allowed_updates=[
            "message",
            "inline_query",
            "chosen_inline_result",
            "callback_query",
        ],
        secret_token=SECRET,
    )
    session = aiohttp.ClientSession()


async def shutdown():
    await bot.delete_webhook()
    await session.close()
    client.close()


@dp.message(Command("delete"))
async def delete(message: Message):
    await bot.delete_sticker_set(message.text.split()[1])


@dp.message(CommandStart())
async def command_start(message: Message):
    await message.answer(
        "Чтобы начать используйте команду /emoji (название канала на твиче)"
    )


@dp.message(Command("emoji", "sticker"))
async def command_emoji(message: Message, state: MongoStorage):
    sticker_type = {"sticker": "regular", "emoji": "custom_emoji"}[
        message.text.split()[0].strip("/").strip()
    ]
    await create_sticker_set(message, state, sticker_type)


@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    if not inline_query.query:
        return
    elif len(inline_query.query.split()) == 1:
        sticker_list = await get_sticker_list(inline_query.query)
        if isinstance(sticker_list, str):
            return
        results = []
        for sticker in sticker_list[:1]:
            url = sticker["urls"][-1]["url"]
            id = extract_id(url)
            db_sticker = await db.stickers.find_one(
                {
                    "sticker_type": "regular",
                    "sticker_id": id,
                }
            )
            if not db_sticker:
                continue
            # print(await bot.get_file(db_sticker["file_id"]))
            # results.append(InlineQueryResultCachedDocument(type="document", id=id, title=sticker["code"], document_file_id=db_sticker["file_id"]))
            # await bot.send_sticker(inline_query.from_user.id, db_sticker["file_id"])
            results.append(InlineQueryResultCachedSticker(type="sticker", id=db_sticker["file_unique_id"], sticker_file_id=db_sticker["file_id"]))
            # results.append(InlineQueryResultCachedSticker(type="photo", id=db_sticker["file_unique_id"], sticker_file_id=db_sticker["file_id"]))
        await bot.answer_inline_query(inline_query.id, results, cache_time=30)
