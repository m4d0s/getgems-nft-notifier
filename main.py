import requests
import asyncio
import sqlite3
import json
import logging
import time

from tg_util import nft_history_notify
from date_util import now, number_to_date, date_to_number
from db_util import fetch_data, update_senders_data
from getgems import get_separate_history_items as history_items, HistoryItem, HistoryType
from aiogram import Bot, Dispatcher, types
# import tracemalloc

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


config_data, senders_data = fetch_data()
bot_token, toncenter_api, ton_api = config_data

bot = Bot(bot_token)
dp = Dispatcher(bot)
# tracemalloc.start()

async def prepare_notify(BOT_TOKEN=bot_token, TONCENTER_API=toncenter_api, TON_API=ton_api, senders_data=senders_data, first = 3):
  new_data = senders_data
  id = -1
  for sender in senders_data:
    id += 1
    history = await history_items(sender[0], TON_API, first)
    # print(history)
    for type in history:
      if type != 'Other':
        for item in history[type]:
          if sender[2] == 0:
            new_data[id][2] = now()
          elif sender[2] < item.time:
              await nft_history_notify(item, chat_id = sender[1], TON_API = TON_API, BOT_TOKEN = BOT_TOKEN)
              time.sleep(0.1)
              new_data[id][2] = item.time
  update_senders_data(tuple(new_data))
      
    
if __name__ == "__main__":
  while True:
    asyncio.run(prepare_notify())
    time.sleep(10)
