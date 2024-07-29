import requests
import asyncio
import sqlite3
import json
import time
import datetime
import aiogram
import logging
from logging import log

from getgems import tonapi_get_data, HistoryItem, HistoryType, address_converter, ContentType, get_nft_info, NftItem
from date_util import number_to_date, log_format_time

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.utils.exceptions import TelegramAPIError, BadRequest

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def send_message(bot_token:str, data:NftItem, chat_id:int, chat_prefix = "-100", retries = 3):
    bot = Bot(bot_token)
    dp = Dispatcher(bot)
    
    # URL картинки
    if data.content_type != ContentType.NotLoaded:
        content_url = data.content.original
    else:
        content_url = None

    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Добавление кнопок
    getgems_button = InlineKeyboardButton("GetGems", url=f"https://getgems.io/user/{data.owner.wallet}")
    tonviever_button = InlineKeyboardButton("TonViever", url=f"https://tonviever.com/{data.owner.wallet}")
    keyboard.add(getgems_button, tonviever_button)
    
    if data.owner.telegram:
        telegram_button = InlineKeyboardButton("Telegram", url="https://t.me/" + data.owner.telegram)
    else:
        telegram_button = InlineKeyboardButton("Telegram @lunaornot", url="https://t.me/lunaornot")
    keyboard.add(telegram_button)
    
    # Adding social links
    temp = []
    for link in data.collection.socialLinks.links:
        temp.append(InlineKeyboardButton(link[1], url=link[0]))
        if len(temp) == 3:
            keyboard.row(*temp)
            temp = []
    if len(temp) > 0:
        keyboard.row(*temp)
    
    text = data.notify_text()
    content = data.get_content_url()
    # Отправка сообщения с фото и клавиатурой
    for i in range(retries + 1):
        try:
            if data.content.type == ContentType.Image:
                await bot.send_photo(
                    chat_id=f"{chat_prefix}{chat_id}",
                    photo=content if "https://" in content else data.get_content_url(original=False),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            elif data.content.type == ContentType.Video:
                await bot.send_video(
                    chat_id=f"{chat_prefix}{chat_id}",
                    video=content if "https://" in content else data.get_content_url(original=False),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                with open('notloaded.png', 'rb') as photo:
                    await bot.send_photo(
                        chat_id=f"-100{chat_id}",
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
            return 0
        except BadRequest:
            await asyncio.sleep(1)
            continue
        except Exception as e:
            log(logging.FATAL, e)
            await asyncio.sleep(1)
            continue

    
async def nft_history_notify(history_item:HistoryItem, chat_id:int, TON_API:str, BOT_TOKEN:str):
    nft = await get_nft_info(history_item)

    if nft.history.type == HistoryType.Sold:
        log(logging.INFO, f'Sold: {nft.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    elif nft.history.type == HistoryType.PutUpForSale:
        log(logging.INFO, f'New NFT on sale: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    elif nft.history.type == HistoryType.PutUpForAuction:
        log(logging.INFO, f'New auction: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    else:
        log(logging.INFO, history_item.address)
    log(logging.INFO, history_item)
    await send_message(BOT_TOKEN, data = nft, chat_id = chat_id)
    