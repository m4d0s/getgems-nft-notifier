import asyncio
import logging
import re
import json
import aiofiles
import aiohttp
from logging import log
from typing import List, Tuple

from date import now, number_to_date,log_format_time
from database import fetch_senders_data, fetch_config_data, get_last_time, get_ad
from database import enter_last_time, enter_price, update_full_senders_data, insert_senders_data
from getgems import get_new_history, coinmarketcap_price, get_nft_info, get_collection_info
from getgems import HistoryItem, HistoryType, ContentType, NftItem, MarketplaceType

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import Message, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('asyncio').setLevel(logging.DEBUG)

translate = json.load(open('getgems.json', 'r', encoding='utf-8'))["translate"]

bot_token = fetch_config_data()[0]
bot = Bot(bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot)

elligble = [HistoryType.Sold, HistoryType.PutUpForSale, HistoryType.PutUpForAuction]
senders_data =  fetch_senders_data()
bot_token, ton_api, cmc_api, last_time = fetch_config_data()
price_ids = [11419,28850,825,1027,1]
app_version = "0.4a"

setup_message = Message()
sender = [None, None, None, None]

def extract_main_domain(url: str):
    # Регулярное выражение для извлечения домена
    domain_regex = re.compile(r'^(?:http[s]?://)?(?:www\.)?([^:/\s]+)')
    match = domain_regex.search(url)
    if match:
      return match.group(1)
    return None 

async def send_notify(bot_token: str, data: NftItem, chat_id: int, lang: str, tz: int, chat_prefix="-100", retries=3):
    if data.sale is None:
        logging.error(f"Sale is None: {data}")
        return -1

    bot = Bot(token=bot_token)

    # Инициализация бота
    bot_info = await bot.get_me()

    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(row_width=2)

    # Добавление кнопок
    getgems_text = f"{translate[lang]['tg_util'][0]} Getgems" if data.marketplace == MarketplaceType.Getgems or "getgems" in data.sale.link else f"{translate[lang]['tg_util'][0]} {extract_main_domain(url=data.sale.link)}"
    getgems_button = InlineKeyboardButton(getgems_text, url=data.sale.link)
    tonviewer_button = InlineKeyboardButton(f"{translate[lang]['tg_util'][1]} TonViewer", url=f"https://tonviever.com/{data.address}")
    keyboard.add(getgems_button, tonviewer_button)

    collection_button = InlineKeyboardButton(f"{translate[lang]['tg_util'][2]} Getgems", url=data.collection.get_url())
    keyboard.add(collection_button)

    ad = list(get_ad())
    if ad[2] == "" or ad[2] == "{bot.link}":
        ad[2] = f"https://t.me/{bot_info.username}"
        ad[1] = translate[lang]['tg_util'][4]
    else:
        ad[1] = f"AD: {ad[1]}"
    ad_button = InlineKeyboardButton(ad[1], url=ad[2])
    keyboard.add(ad_button)

    setup_button = InlineKeyboardButton(text=f"{translate[lang]['tg_util'][3]}", url=f"https://t.me/{bot_info.username}?startgroup=true&admin=post_messages+edit_messages+delete_messages")
    keyboard.add(setup_button)

    text = data.notify_text(tz=tz, lang=lang)
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
                async with aiofiles.open(data.content.original, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=f"{chat_prefix}{chat_id}",
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
            return 0
        except Exception as e:
            logging.error(e)
            await asyncio.sleep(1)
            continue

    return -1
        
async def nft_history_notify(session:aiohttp.ClientSession, history_item: HistoryItem, chat_id: int, TON_API: str, BOT_TOKEN: str, lang: str, tz: int = 0):
    try:
        # Получение информации о NFT
        nft = await get_nft_info(session, history_item)
        if nft is None:
            logging.error(f"Failed to get NFT info: {history_item}")
            return

        # Логирование в зависимости от типа истории
        if nft.history.type == HistoryType.Sold:
            logging.info(f'Sold: {nft.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForSale:
            logging.info(f'New NFT on sale: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForAuction:
            logging.info(f'New auction: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        else:
            logging.info(f"Another action happened: {history_item}")
            return

        # Отправка уведомления
        await send_notify(BOT_TOKEN, data=nft, chat_id=chat_id, lang=lang, tz=tz)
        
    except Exception as e:
        logging.error(f"Error in nft_history_notify: {e}")

# Обработчик добавления новых участников
@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS, commands=["start", "setup"])
async def new_chat_setup(message: types.Message):
    for new_member in message.new_chat_members:
        logging.info(f"New member added: {new_member.id}")
        if new_member.id == bot.id:
            logging.info(f"Bot added to a new chat: {message.chat.id}")
            try:
                await message.delete()  # Удаляем сообщение о добавлении бота в чат
            except Exception as e:
                logging.error(f"Failed to delete the message: {e}")

            setup_message = await bot.send_message(
                message.chat.id,
                "Привет! Пожалуйста, выберите язык коллекции",
                reply_markup=language_keyboard()
            )
            sender[1] = message.chat.id
            logging.info(f"Setup message sent with ID: {setup_message.message_id}")

def language_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for language in translate:
        keyboard.add(InlineKeyboardButton(translate[language]["Name"], callback_data=language))
    return keyboard

@dp.callback_query_handler(lambda call: call.data in [language for language in translate])
async def on_language_selected(call: CallbackQuery):
    language_selected = call.data
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(call.message.chat.id)]
    sender[3] = language_selected
    if call.from_user.id in can_setup:
        await call.message.edit_text("Спасибо! Теперь введите адрес NFT коллекции ответом на это сообщение")
    else:
        await call.answer("У вас нет прав на выполнение этой команды", show_alert=True)
@dp.message_handler(lambda message: message.reply_to_message and message.reply_to_message.message_id == setup_message.message_id)
async def handle_reply(message: types.Message):
    collection = await get_collection_info(message.text)
    if collection and collection.address == message.text:
        sender[0] = collection.address
        sender[2] = message.from_user.id
        insert_senders_data(sender)
        await message.reply("Спасибо! Теперь бот настроен, но вы всегда можете настроить его дополнительно по команде /settings")
    else:
        await message.reply("Некорректный адрес NFT коллекции. Пожалуйста, введите еще раз.")



async def run_periodically(interval, func, *args, **kwargs):
    while True:
        await func(*args, **kwargs)
        await asyncio.sleep(interval)

async def prepare_notify(session:aiohttp.ClientSession, BOT_TOKEN=bot_token, TON_API=ton_api, CMC_API=cmc_api, senders_data=senders_data, first = 10):
    count = 0
    history_items = []

    # Сбор истории для каждого отправителя
    async def gather_history_for_sender(sender: Tuple, index: int) -> None:
        nonlocal history_items
        history = await get_new_history(session, sender, TON_API, first)
        for i in history:
            history_items.append((i, sender[1], sender[2], index, sender[5], sender[6]))

    # Параллельная сборка истории
    tasks = [gather_history_for_sender(sender, index) for index, sender in enumerate(senders_data)]
    await asyncio.gather(*tasks)

    # Обработка и уведомление
    async def process_history_item(history_item: Tuple) -> None:
        nonlocal count
        history, chat_id, _, sender_index, lang, tz = history_item
        if history.type in elligble:
            if history.time == 0:
                senders_data[sender_index][2] = now()
            else:
                await nft_history_notify(session, history, chat_id, TON_API, BOT_TOKEN, lang, tz)
                count += 1
                senders_data[sender_index][2] = history.time

    # Параллельная обработка истории
    sorted_history_items = sorted(history_items, key=lambda x: int(x[0].time) + x[0].type.value, reverse=True)
    await asyncio.gather(*(process_history_item(item) for item in sorted_history_items))

    # Обновление данных отправителей и времени
    update_full_senders_data(senders_data)
    enter_last_time()

    return count
        
async def enter_cmc_price():
    price = coinmarketcap_price(cmc_api, price_ids)
    enter_price(price)
    
async def history_notify(session:aiohttp.ClientSession ,counter=0):
    logging.info("Start checking for new history data...")
    count = await prepare_notify(session)
    logging.info(f"Notification process ended, total notifications: {count}, now timestamp" + 
                f" {get_last_time()} ({number_to_date(get_last_time())})")

async def main():
    async with aiohttp.ClientSession() as session:
        
        logging.info("\n\n----- Start of new session, version: " + app_version +
                    ", now timestamp: "  + str(get_last_time()) + 
                    ", date: " + number_to_date(get_last_time()) +" -----")

        # Запускаем асинхронные задачи
        asyncio.create_task(run_periodically(300, enter_cmc_price))
        asyncio.create_task(run_periodically(5, history_notify, session))

        # enter_price(coinmarketcap_price(cmc_api, price_ids))

        await dp.start_polling()

if __name__ == '__main__':
    # Запуск асинхронной функции main
    asyncio.run(main())