import asyncio
import logging
import re
import json
import aiofiles
import aiohttp
from typing import List, Tuple

from date import now, number_to_date, log_format_time
from database import (
    fetch_senders_data, fetch_config_data, get_last_time, get_ad, is_setup_by_chat_id,
    enter_last_time, enter_price, update_full_senders_data, insert_senders_data,
    delete_senders_data, get_senders_data_by_id, return_chat_language
)
from getgems import (
    get_new_history, coinmarketcap_price, get_nft_info, get_collection_info, address_converter, short_address,
    HistoryItem, HistoryType, ContentType, NftItem, MarketplaceType, AddressType
)

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import Message, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile
from aiogram.utils import executor

# Configure logging
logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('asyncio').setLevel(logging.DEBUG)

local = json.load(open('getgems.json', 'r', encoding='utf-8'))['local']
translate = json.load(open('getgems.json', 'r', encoding='utf-8'))["translate"]

# Bot setup
bot_token, ton_api, cmc_api, last_time = fetch_config_data()
bot = Bot(bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot)

elligible = [HistoryType.Sold, HistoryType.PutUpForSale, HistoryType.PutUpForAuction]
senders_data = fetch_senders_data()
price_ids = [11419, 28850, 825, 1027, 1]
app_version = "0.5a"

setup_message = Message()
sender = [None, None, None, None, None]


# Helpful functions
def extract_main_domain(url: str):
    domain_regex = re.compile(r'^(?:http[s]?://)?(?:www\.)?([^:/\s]+)')
    match = domain_regex.search(url)
    return match.group(1) if match else None

async def enter_cmc_price():
    price = coinmarketcap_price(cmc_api, price_ids)
    enter_price(price)

async def run_periodically(interval, func, *args, **kwargs):
    while True:
        try:
            await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in periodic function {func.__name__}: {e}")
        await asyncio.sleep(interval)



# History notification functions
async def send_notify(bot_token: str, data: NftItem, chat_id: int, lang: str, tz: int, retries=3):
    if data.sale is None:
        logging.error(f"Sale is None: {data}")
        return -1

    bot = Bot(token=bot_token)
    bot_info = await bot.get_me()
    keyboard = InlineKeyboardMarkup(row_width=2)

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

    for _ in range(retries + 1):
        try:
            if data.content.type == ContentType.Image:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=content if "https://" in content else data.get_content_url(original=False),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            elif data.content.type == ContentType.Video:
                await bot.send_video(
                    chat_id=chat_id,
                    video=content if "https://" in content else data.get_content_url(original=False),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                async with aiofiles.open(data.content.original, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
            return 0
        except Exception as e:
            logging.error(e)
            await asyncio.sleep(1)
    return -1

async def nft_history_notify(session: aiohttp.ClientSession, history_item: HistoryItem, chat_id: int, TON_API: str, BOT_TOKEN: str, lang: str, tz: int = 0):
    try:
        nft = await get_nft_info(session, history_item)
        if nft is None:
            logging.error(f"Failed to get NFT info: {history_item}")
            return
        if nft.history is None:
            nft.history = history_item

        if nft.history.type == HistoryType.Sold:
            logging.info(f'Sold: {nft.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForSale:
            logging.info(f'New NFT on sale: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForAuction:
            logging.info(f'New auction: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        else:
            logging.info(f"Another action happened: {history_item}")
            return

        await send_notify(BOT_TOKEN, data=nft, chat_id=chat_id, lang=lang, tz=tz)
        
    except Exception as e:
        logging.error(f"Error in nft_history_notify: {e}")

async def prepare_notify(session: aiohttp.ClientSession, BOT_TOKEN=bot_token, TON_API=ton_api, CMC_API=cmc_api, senders_data=senders_data, first=10):
    count = 0
    history_items = []

    async def gather_history_for_sender(sender: Tuple, index: int) -> None:
        nonlocal history_items
        history = await get_new_history(session, sender, TON_API, first)
        for i in history:
            history_items.append((i, sender[1], sender[2], index, sender[5], sender[6]))

    tasks = [gather_history_for_sender(sender, index) for index, sender in enumerate(senders_data)]
    await asyncio.gather(*tasks)

    async def process_history_item(history_item: Tuple) -> None:
        nonlocal count
        history, chat_id, _, sender_index, lang, tz = history_item
        if history.type in elligible:
            if history.time == 0:
                senders_data[sender_index][2] = now()
            else:
                await nft_history_notify(session, history, chat_id, TON_API, BOT_TOKEN, lang, tz)
                count += 1
                senders_data[sender_index][2] = history.time

    sorted_history_items = sorted(history_items, key=lambda x: int(x[0].time) + x[0].type.value, reverse=True)
    await asyncio.gather(*(process_history_item(item) for item in sorted_history_items))

    update_full_senders_data(senders_data)
    enter_last_time()

    return count

async def history_notify(session: aiohttp.ClientSession, counter=0):
    logging.info("Start checking for new history data...")
    count = await prepare_notify(session)
    logging.info(f"Notification process ended, total notifications: {count}, now timestamp {get_last_time()} ({number_to_date(get_last_time())})")
 
 
        
# Setup functions
@dp.message_handler(commands=["start"])
async def start_setup(message: types.Message):
    if not(message.chat.type == types.ChatType.PRIVATE or \
           is_setup_by_chat_id(message.chat.id)):
        
        logging.info(f"Bot added to a new chat: {message.chat.id}")
        try:
            await message.delete()
        except Exception as e:
            logging.error(f"Failed to delete the message: {e}")
        global setup_message
        setup_message = await bot.send_message(
            chat_id=message.chat.id,
            text="Hi! Please, choose your language",
            reply_markup=language_keyboard()
        )
        sender[1] = message.chat.id
        logging.info(f"Setup message sent with ID: {setup_message.message_id}")
    elif not message.chat.type == types.ChatType.PRIVATE:
        list_notifications(message)
        pass
    
@dp.message_handler(commands=["nftlist"])
async def list_notifications(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        senders = get_senders_data_by_id(message.chat.id)
        text = f"<b>{translate[return_chat_language(message.chat.id)]['settings'][0]}</b>\n"
        keyboard = InlineKeyboardMarkup(row_width=1)
        for sender in senders:
            keyboard.add(InlineKeyboardButton(f'{short_address(sender[0])}', 
                                                callback_data=f'setup_{sender[0]}'))
        await bot.send_message(chat_id=message.chat.id, 
                            text=text, 
                            reply_markup=keyboard,
                            parse_mode=ParseMode.HTML)
        try :
            await message.delete()
        except Exception as e:
            logging.error(f"Failed to delete the message: {e}")

@dp.callback_query_handler(lambda query: query.data.startswith('setup_'))
async def settings(query: types.CallbackQuery):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(query.message.chat.id)]
    if query.from_user.id in can_setup:
        text = f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][1]}</b>\n\n"
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=query.data[6:], chat_id=query.message.chat.id)
        if collection and address_converter(collection.address) == address_converter(query.data[6:]):
            text += f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][2]}</b>{collection.name}\n"
            text += f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][3]}</b><code>{collection.address}</code>\n"
            text += f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][4]}</b>{collection.owner.link_user_text()}\n\n"
            text += f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][5]}</b>{collection.description}\n"
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                # InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][6]}", callback_data=f"edit_{query.data[6:]}"),
                InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][7]}", callback_data=f"delete_{query.data[6:]}")
                )
            keyboard.add(InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][8]}", callback_data="list_notifications"))
            await bot.edit_message_text(text=text, chat_id=query.message.chat.id, message_id=query.message.message_id, parse_mode=ParseMode.HTML)             

@dp.message_handler(commands=["nftadd"])
async def add_notification(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        args = message.text.split()[1:]
        senders = get_senders_data_by_id(message.chat.id)
        addresses = [address_converter(sender[0]) for sender in senders]
        if len(args) != 1:
            await bot.send_message(message.chat.id, "Input command again")
            return
        if address_converter(args[0]) in addresses:
            await bot.send_message(message.chat.id, f"Collection {args[0]} already added")
            return
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for code in translate:
            b = InlineKeyboardButton(text=translate[code]['Name'], 
                                    callback_data=f"addnotif_{code}_{args[0]}")
            keyboard.add(b)
        await bot.send_message(message.chat.id, f"Choose language for notification on collection <b>{args[0]}</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        args = message.text.split()[1:]
        await bot.send_message(message.chat.id, f"Collection {args[0]} not found, input command again")
        await message.delete()

@dp.callback_query_handler(lambda call: call.data.startswith('addnotif_'))
async def add_notification_call(query: types.CallbackQuery):
    args = query.data.split('_')[1:]
    await query.answer(f"Processing to add and verificate the collection ({args[1]}), please wait a few seconds...", show_alert=True)
    async with aiohttp.ClientSession() as session:
        collection = await get_collection_info(session=session, collection_address=args[1])
    if collection and address_converter(collection.address) == address_converter(args[1]):
        sender = [args[0], query.message.from_user.id, args[1], query.message.chat.id, " ".join(args[2:]), collection.name]
        insert_senders_data(sender)
        await bot.send_message(query.message.chat.id, f"Notification for collection <code>{args[1]}</code> added", parse_mode=ParseMode.HTML)
        await add_notification(query.message)
    else:
        await bot.send_message(query.message.chat.id, f"Collection <code>{args[1]}</code> not found", parse_mode=ParseMode.HTML)
        
@dp.message_handler(commands=["nftdel"])
async def delete_notification(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        args = message.text.split()[1:]
        senders = get_senders_data_by_id(message.chat.id)
        addresses = [sender[0] for sender in senders]
        if len(args) != 1:
            await bot.send_message(message.chat.id, f"Input command again")
            return
        if args[0] not in addresses:
            await bot.send_message(message.chat.id, f"Collection <code>{args[0]}</code> not found", parse_mode=ParseMode.HTML)
            return
        delete_senders_data(args[0], message.chat.id)
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=args[0])
            await bot.send_message(message.chat.id, f"Notification for collection <code>\"{collection.name}\"</code> deleted", parse_mode=ParseMode.HTML)
            await message.delete()
    else:
        await message.delete()
    
def language_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    for language in translate:
        keyboard.add(InlineKeyboardButton(translate[language]["Name"], callback_data=language))
    return keyboard

@dp.callback_query_handler(lambda call: call.data in translate)
async def on_language_selected(call: CallbackQuery):
    language_selected = call.data
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(call.message.chat.id)]
    sender[3] = language_selected
    if call.from_user.id in can_setup:
        await call.message.edit_text(translate[language_selected]["setup"][0])
    else:
        await call.answer(translate[language_selected]["setup"][1], show_alert=True)
        
@dp.message_handler(lambda message: message.reply_to_message and message.reply_to_message.message_id == setup_message.message_id)
async def handle_reply(message: types.Message):
    async with aiohttp.ClientSession() as session:
        collection = await get_collection_info(session=session, collection_address=message.text)
    if collection and address_converter(collection.address) == address_converter(message.text):
        sender[0] = message.text
        sender[2] = message.from_user.id
        sender[4] = collection.name
        insert_senders_data(sender)
        await message.reply(translate[sender[3]]["setup"][2])
    else:
        await message.reply(translate[sender[3]]["setup"][3])
        


# just inline
@dp.inline_handler()
async def inline_link_preview(query: types.InlineQuery):
    address = address_converter(query.query, format=AddressType.Bouncable)
    if not address:
        return
    async with aiohttp.ClientSession() as session:
        nft = asyncio.create_task(get_nft_info(session, address))
        await asyncio.sleep(5)
        if nft.done():
            nft = nft.result()
        else:
            nft = None
    if not nft:
        link = f'https://getgems.io/'
        title = 'Cannot load info about nft'
        desc = 'try again later'
        thumb = "https://cache.tonapi.io/imgproxy/LyP5sSl_-zzlYjxwIrizRjzuFPQt_2abAT9u4-0W52Q/rs:fill:200:200:1/g:no/aHR0cHM6Ly9nYXMxMTEuczMuYW1hem9uYXdzLmNvbS9pbWFnZXMvM2U3YzU1ZjYxODg3NDlmOGI0NjdiOTY5YzczZjA0NzcucG5n.webp" 
        
        inline_button = InlineKeyboardButton(text="Getgems", url=link)
        inline_keyboard = InlineKeyboardMarkup().add(inline_button)
        
        result = types.InlineQuery
    
        result = types.InlineQueryResultArticle(
                id='1',
                title=title,
                description=desc,
                thumb_url=thumb,
                reply_markup=inline_keyboard,
                input_message_content=types.InputTextMessageContent(message_text="Failed to load NFT info"),
            )
        
    else:
        link = f'https://getgems.io/nft/{address}'
        title = f'{nft.name} from {nft.collection.name}'
        desc = f'{nft.description}'
        thumb = nft.content.get_url()
    
        inline_button = InlineKeyboardButton(text="See on Getgems", url=link)
        inline_keyboard = InlineKeyboardMarkup().add(inline_button)
        
        result = types.InlineQueryResultPhoto(
            id='1',
            photo_url=thumb,
            thumb_url=thumb,
            title=title,
            description=desc,
            reply_markup=inline_keyboard,
            input_message_content=types.InputTextMessageContent(
                message_text=nft.notify_text(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        )    
        
    await query.answer([result], cache_time=1)
    
    
    
# just main
async def main():
    async with aiohttp.ClientSession() as session:
        logging.info(f"\n\n----- Start of new session, version: {app_version}, now timestamp: {get_last_time()}, date: {number_to_date(get_last_time())} -----")

        asyncio.create_task(run_periodically(300, enter_cmc_price))
        asyncio.create_task(run_periodically(5, history_notify, session))

        await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
