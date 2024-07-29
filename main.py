import requests
import asyncio
import sqlite3
import json
import logging
import time

from tg_util import nft_history_notify
from db_util import fetch_data, update_senders_data, get_last_time, enter_last_time, enter_price
from getgems import get_separate_history_items as new_history_items, coinmarketcup_price
from aiogram import Bot, Dispatcher
import sched
import threading
import tracemalloc

from date_util import now, number_to_date, log_format_time
logging.basicConfig(
    filename=f'bot.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

config_data, senders_data = fetch_data()
bot_token, cmc_api, ton_api, last_time, ton_price = config_data

bot = Bot(bot_token)
dp = Dispatcher(bot)

def run_periodically(interval, func, *args, **kwargs):
    s = sched.scheduler(time.time, time.sleep)

    def periodic():
        enter_price(func(*args, **kwargs))
        s.enter(interval, 1, periodic)

    s.enter(interval, 1, periodic)
    s.run()

async def prepare_notify(BOT_TOKEN=bot_token, TON_API=ton_api, senders_data=senders_data, first = 10):
  new_data = senders_data
  id = -1
  count = 0
  for sender in senders_data:
    id += 1
    history = await new_history_items(sender[0], TON_API, first)
    # logging.info(history)
    for type in history:
      if type != 'Other':
        for item in history[type]:
          if sender[2] == 0:
            new_data[id][2] = now()
          else:
              await nft_history_notify(item, chat_id = sender[1], TON_API = TON_API, BOT_TOKEN = BOT_TOKEN)
              count += 1
              new_data[id][2] = item.time
  update_senders_data(tuple(new_data))
  enter_last_time()
  return count
    
if __name__ == "__main__":
  
  thread = threading.Thread(target=run_periodically, args=(300, coinmarketcup_price))
  thread.daemon = True  # Позволяет завершать поток вместе с основным программным процессом
  thread.start()
  
  while True:
    logging.info("Start checking for changes...")
    count = asyncio.run(prepare_notify())
    logging.info(f"Notification process ended, total notifications: {count}, now timestamp" + 
                 f" {get_last_time()} ({number_to_date(get_last_time())})")
    time.sleep(10)
