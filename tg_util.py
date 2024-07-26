import requests
import asyncio
import sqlite3
import json
import time
import datetime
import aiogram
import logging

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from getgems import tonapi_get_data, HistoryItem, HistoryType, address_converter, AddressType
from date_util import number_to_date

from aiogram import Bot, Dispatcher, types
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiogram.enums import ParseMode
# from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor


async def send_message(bot_token:str, data:HistoryItem, chat_id:int):
    bot = Bot(bot_token)
    dp = Dispatcher(bot)
    
    # URL картинки
    photo_url = 'https://example.com/path/to/your/image.jpg'

    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавление кнопок
    buttons = []
    for link in data.social:
        buttons.append(InlineKeyboardButton(link, url=link))
        InlineKeyboardButton("Button 1", callback_data="button1")
    button2 = InlineKeyboardButton("Button 2", callback_data="button2")
    button3 = InlineKeyboardButton("Button 3", callback_data="button3")
    
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
    tonapi_data = await tonapi_get_data(TON_API, history_item.address)
    # print(tonapi_data)
    print(tonapi_data.collection.address)
    collection_add = f"{address_converter(tonapi_data.collection.address.to_raw(), format=AddressType.Unbouncable)}  ({tonapi_data.collection.name})"

    if history_item.type == HistoryType.Sold:
        print(f'Sold: {history_item.address} on collection {collection_add} ({number_to_date(history_item.time)})')
    elif history_item.type == HistoryType.PutUpForSale:
        print(f'New NFT on sale: {history_item.address} on collection {collection_add} ({number_to_date(history_item.time)})')
    elif history_item.type == HistoryType.PutUpForAuction:
        print(f'New auction: {history_item.address} on collection {collection_add} ({number_to_date(history_item.time)})')
    
    print(history_item)
    # await send_message(BOT_TOKEN, f'{history_item.address} on collection {collection_add}', history_item.address)
    