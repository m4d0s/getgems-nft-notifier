import asyncio
import sched
import threading
import logging
import time

from tg_util import nft_history_notify
from date_util import now, number_to_date,log_format_time
from db_util import fetch_senders_data, fetch_config_data, get_last_time
from db_util import enter_last_time, enter_price
from getgems import get_new_history, coinmarketcap_price, HistoryType
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

logging.basicConfig(
  filename=f'logs/{log_format_time()}.log',
  level=logging.INFO, 
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

elligble = [HistoryType.Sold, HistoryType.PutUpForSale, HistoryType.PutUpForAuction]
senders_data =  fetch_senders_data()
bot_token, ton_api, cmc_api, last_time = fetch_config_data()
price_ids = [11419,28850,825,1027,1]
app_version = "0.2a"

bot = Bot(bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot)

def run_periodically(interval, func, *args, **kwargs):
  s = sched.scheduler(time.time, time.sleep)

  def periodic():
    enter_price(func(*args, **kwargs))
    s.enter(interval, 1, periodic)

  s.enter(interval, 1, periodic)
  s.run()

async def prepare_notify(BOT_TOKEN=bot_token, TON_API=ton_api, CMC_API=cmc_api, senders_data=senders_data, first = 10, counter = 0):
  count = 0
  history_items = []
  id = -1
  for sender in senders_data:
    id += 1
    history = await get_new_history(sender, TON_API, first)
    for i in history:
      history_items.append((i, sender[1], sender[2], id, sender[5], sender[6]))
  
  for history in sorted(history_items, key=lambda x: int(x[0].time) + x[0].type.value, reverse=True):
    if history[0].type in elligble:
      if history[2] == 0 and counter == 0:
        senders_data[history[3]][2] = now()
      else:
        await nft_history_notify(history[0], chat_id = history[1], TON_API = TON_API, BOT_TOKEN = BOT_TOKEN, lang = history[4], tz = history[5])
        count += 1
        senders_data[history[3]][2] = history[0].time #+ 1 
  enter_last_time()
  counter += 1
  return count

async def main():
  
  logging.info("\n\n----- Start of new session, version: " + app_version +
               ", now timestamp: "  + str(get_last_time()) + 
               ", date: " + number_to_date(get_last_time()) +" -----")
  
  thread = threading.Thread(target=run_periodically, args=(300, coinmarketcap_price, cmc_api, price_ids))
  thread.daemon = True  # Позволяет завершать поток вместе с основным программным процессом
  thread.start()
  
  enter_price(coinmarketcap_price(cmc_api, price_ids))
  notify_counter = 0
  while True:
    logging.info("Start checking for new history data...")
    count = await prepare_notify(counter=notify_counter)
    logging.info(f"Notification process #{notify_counter} ended, total notifications: {count}, now timestamp" + 
                f" {get_last_time()} ({number_to_date(get_last_time())})")
    time.sleep(15)

if __name__ == '__main__':
  asyncio.run(main())