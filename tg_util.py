import requests
import asyncio
import sqlite3
import json
import time
import datetime
import aiogram
import logging
from logging import log

from getgems import tonapi_get_data, HistoryItem, HistoryType, address_converter, AddressType, get_nft_info
from date_util import number_to_date

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

logging.basicConfig(
    filename=f'bot.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def send_message(bot_token:str, data:HistoryItem, chat_id:int):
    bot = Bot(bot_token)
    dp = Dispatcher(bot)
    
    # URL картинки
    photo_url = 'https://example.com/path/to/your/image.jpg'

    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавление кнопок
    buttons = []
    getgems_button = InlineKeyboardButton("GetGems", url="https://getgems.io")
    tonviever_button = InlineKeyboardButton("TonViever", url="https://tonviever.com")
    buttons.append([getgems_button, tonviever_button])
    telegram_button = InlineKeyboardButton("Telegram", url=data.social[0])
    buttons.append([telegram_button])
    
    temp = []
    for link in data.social:
        if len(temp) == 3:
            buttons.append(temp)
            temp = []
        buttons.append(InlineKeyboardButton(link, url=link))
    if len(temp) > 0:
        buttons.append(temp)
    
    keyboard.add(buttons)
    
    text=''

    # Отправка сообщения с фото и клавиатурой
    await bot.send_photo(
        chat_id=chat_id,
        photo=photo_url,
        caption=text,
        reply_markup=keyboard
    )
    
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
    # await send_message(BOT_TOKEN, f'{history_item.address} on collection {collection_add}', history_item.address)
    