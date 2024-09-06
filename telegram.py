import asyncio
import re
import json
import aiofiles
import traceback
import aiohttp
from typing import Tuple

from date import now, number_to_date
from database import (fetch_config_data, get_last_time, get_ad, is_setup_by_chat_id,
                    enter_last_time, enter_price, update_senders_data, 
                    delete_senders_data, return_chat_language, get_logger,
                    enter_cache, get_cache, get_sender_data, fetch_all_senders, set_sender_data)
from getgems import (
    get_new_history, get_nft_info, get_collection_info, address_converter, short_address,
    HistoryItem, HistoryType, ContentType, NftItem, MarketplaceType, AddressType
)
from responce import coinmarketcap_price
from proxy import prepare

from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, ChatNotFound, BotBlocked, 
                                      MessageToEditNotFound, MessageCantBeDeleted, MessageCantBeEdited, UserDeactivated)


logger = get_logger()

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
local = config.pop('local')
translate = config.pop('translate')
snippet = config.pop('snippets')

# Bot setup
config = fetch_config_data()
bot = Bot(config['bot_api'])
dp = Dispatcher(bot)

elligible = [HistoryType.Sold, HistoryType.PutUpForSale, HistoryType.PutUpForAuction]
price_ids = [11419, 28850, 825, 1027, 1]
app_version = "0.8a"

class FilesType:
    NONE = 0
    IMAGE = 1
    VIDEO = 2
    DOCUMENT = 3


# Helpful functions
def extract_main_domain(url: str):
    domain_regex = re.compile(r'^(?:http[s]?://)?(?:www\.)?([^:/\s]+)')
    match = domain_regex.search(url)
    return match.group(1) if match else None

async def enter_cmc_price():
    price = await coinmarketcap_price(config['cmc_api'], price_ids)
    enter_price(price)

def html_back_escape(text:str) -> str:
    return str(text).replace('&lt;', '＜').replace('&gt;', '＞').replace('&amp;', '＆')

async def run_periodically(interval, func, *args, **kwargs):
    while True:
        try:
            await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in periodic function {func.__name__}: {e}")
        await asyncio.sleep(interval)



#Messagee funcs
async def try_to_delete(chat_id:int, message_id:int) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to delete in chat ' + str(chat_id))
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except MessageToDeleteNotFound:
        return False
    except MessageCantBeDeleted:
        return False
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def try_to_edit(text:str, chat_id:int, message_id:int, keyboard: InlineKeyboardMarkup = None) -> bool:
    if message_id is None or message_id == 0:
        logger.debug('Message ID is None to edit in chat ' + str(chat_id))
        return False
    try:
        await bot.edit_message_text(text, chat_id, message_id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return True
    except MessageNotModified:
        return False
    except MessageToEditNotFound:
        return False
    except MessageCantBeEdited:
        return False
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def new_message(text: str, chat_id: int, keyboard: InlineKeyboardMarkup = None, disable_preview:bool = True, file_type: FilesType = FilesType.NONE, file = None, parse_mode = ParseMode.HTML) -> types.Message:
    try:
        if file_type == FilesType.IMAGE:
            return await bot.send_photo(text=html_back_escape(text), 
                                         chat_id=chat_id, 
                                         parse_mode=parse_mode, 
                                         disable_web_page_preview=disable_preview, 
                                         reply_markup=keyboard, 
                                         photo=file)
        elif file_type == FilesType.VIDEO:
            return await bot.send_video(text=html_back_escape(text), 
                                         chat_id=chat_id, 
                                         parse_mode=parse_mode, 
                                         disable_web_page_preview=disable_preview, 
                                         reply_markup=keyboard, 
                                         video=file)
        elif file_type == FilesType.DOCUMENT:
            return await bot.send_document(text=html_back_escape(text), 
                                           chat_id=chat_id, 
                                           parse_mode=parse_mode, 
                                           disable_web_page_preview=disable_preview, 
                                           reply_markup=keyboard, 
                                           document=file)
        elif file_type == FilesType.NONE:
            return await bot.send_message(text=html_back_escape(text), 
                                          chat_id=chat_id, 
                                          parse_mode=parse_mode, 
                                          disable_web_page_preview=disable_preview, 
                                          reply_markup=keyboard)
    # except MessageIsTooLong:
    #     logger.warning('Message is too long to send in chat ' + str(chat_id))
    except UserDeactivated:
        logger.warning("User ({user_id}) deactivated".format(user_id=chat_id))
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
    except ChatNotFound:
        logger.warning("Chat ({user_id}) not found".format(user_id=chat_id))
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
  
async def send_error_message(chat_id:int, message:str, e:Exception = None, only_dev:bool = False) -> types.Message:
    cache = await get_cache(chat_id) ##cache
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Close", callback_data='delete_message'))
    
    cache['process'] = True
    if cache['error']:
        await try_to_delete(chat_id, cache['error'])
    if cache['welcome']:
        await try_to_delete(chat_id, cache['welcome'])
        cache['welcome'] = None
        
    if e is not None:
        err_t = f'Error: {e}' if str(e) else 'Error: No details'
        logger.error(traceback.format_stack()[-2].split('\n')[0].strip() + f'\t{err_t}')
    if only_dev:
        ERROR_MESS = await new_message(text=message, chat_id=config['dev'], keyboard=keyboard)
    else:
        ERROR_MESS = await new_message(text=message, chat_id=chat_id, keyboard=keyboard)
    
    cache['error'] = ERROR_MESS.message_id
    await enter_cache(chat_id, cache) ##write
    return ERROR_MESS

@dp.callback_query_handler(lambda c: c.data == 'delete_message')
async def delete_message(call: types.CallbackQuery):
    await try_to_delete(call.message.chat.id, call.message.message_id)



# History notification functions
async def send_notify(data: NftItem, chat_id: int, lang: str, tz: int, retries=3):
    if data.sale is None:
        logger.error(f"Sale is None: {data}")
        return -1

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
                photo = content if "https://" in content else data.get_content_url(original=False)
                await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.IMAGE, file=photo)
            elif data.content.type == ContentType.Video:
                video = content if "https://" in content else data.get_content_url(original=False)
                await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.VIDEO, file=video)
            else:
                async with aiofiles.open(data.content.original, 'rb') as photo:
                    await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.DOCUMENT, file=photo)
            return True
        except Exception as e:
            logger.error(e)
            await asyncio.sleep(1)
    return False

async def nft_history_notify(session: aiohttp.ClientSession, history_item: HistoryItem, chat_id: int, lang: str, tz: int = 0):
    try:
        nft = await get_nft_info(session, history_item)
        if nft is None:
            logger.error(f"Failed to get NFT info: {history_item}")
            return
        if nft.history is None:
            nft.history = history_item

        if nft.history.type == HistoryType.Sold:
            logger.info(f'Sold: {nft.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForSale:
            logger.info(f'New NFT on sale: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        elif nft.history.type == HistoryType.PutUpForAuction:
            logger.info(f'New auction: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
        else:
            logger.info(f"Another action happened: {history_item}")
            return

        await send_notify(data=nft, chat_id=chat_id, lang=lang, tz=tz)
        
    except Exception as e:
        logger.error(f"Error in nft_history_notify: {e}")

async def prepare_notify(session: aiohttp.ClientSession, first=10):
    count = 0
    history_items = []
    senders_data = fetch_all_senders()

    async def gather_history_for_sender(sender: dict) -> None:
        nonlocal history_items
        cache = get_cache(sender['telegram_user'])
        try:
            chat = await bot.get_chat(sender['telegram_id'])
        except Exception as e:
            chat = None
            logger.error(f"Error in prepare_notify: {e}")
        if not chat:
            delete_senders_data(sender['collection_address'], sender['telegram_id'])
            await new_message(text="You delete me from chat? please let me back", chat_id=sender['telegram_user'])
            return
        elif chat.permissions.can_send_messages is False and not cache.get(f'{sender["telegram_id"]}_error'):
            # delete_senders_data(sender['collection_address'], sender['telegram_id'])
            MESS = await new_message(text="You dont give me permission to send messages", chat_id=sender['telegram_user'])
            cache[f'{sender["telegram_id"]}_error'] = MESS.message_id
            return
        history = await get_new_history(session, sender, config['ton_api'], first)
            
        for h in history:
            history_items.append((h, sender))
            
    senders_data = [sender for sender in senders_data if all(sender[x] is not None for x in sender)]

    tasks = [gather_history_for_sender(sender) for sender in senders_data]
    await asyncio.gather(*tasks)

    async def process_history_item(history_item: Tuple) -> None:
        nonlocal count
        history, sender = history_item
        if history.type in elligible:
            if history.time == 0:
                senders_data[sender['index']]['last_time'] = now()
            else:
                await nft_history_notify(session=session, 
                                         history_item=history, 
                                         chat_id=sender['telegram_id'], 
                                         lang=sender['language'], 
                                         tz=sender['timezone'])
                count += 1
                senders_data[sender['index']]['last_time'] = history.time

    sorted_history_items = sorted(history_items, key=lambda x: int(x[0].time) + x[0].type.value, reverse=True)
    await asyncio.gather(*(process_history_item(item) for item in sorted_history_items))

    update_senders_data(senders_data)
    enter_last_time()

    return count

async def history_notify(counter=0):
    async with aiohttp.ClientSession() as session:
        logger.info("Start checking for new history data...")
        count = await prepare_notify(session)
        logger.info(f"Notification process ended, total notifications: {count}, now timestamp {get_last_time()} ({number_to_date(get_last_time())})")
 
 
 
 
        
# Setup functions
def language_keyboard(id:int):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for language in translate:
        keyboard.add(InlineKeyboardButton(translate[language]["Name"], callback_data=f'lang_{language}_{id}'))
    return keyboard

@dp.message_handler(commands=["start"])
async def start_setup(message: types.Message):
    if not(message.chat.type == types.ChatType.PRIVATE or \
           is_setup_by_chat_id(message.chat.id)):
        
        logger.info(f"Bot added to a new chat: {message.chat.id}")
        try:
            await try_to_delete(message.chat.id, message.message_id)
        except Exception as e:
            logger.error(f"Failed to delete the message: {e}")
        senders = get_sender_data(chat_id=message.chat.id)
        sender = senders[0]
        sender['telegram_id'] = message.chat.id
        id = set_sender_data(sender)
        setup_message = await new_message (chat_id=message.chat.id, text="Hi! Please, choose your language", keyboard=language_keyboard(id))
        messid = setup_message.message_id


        enter_cache(message.chat.id, {"setup": messid, 'sender': id})
        logger.info(f"Setup message sent with ID: {messid}")
    elif not message.chat.type == types.ChatType.PRIVATE:
        await list_notifications(message)
        pass
    
@dp.callback_query_handler(lambda call: call.data.startswith('lang_'))
async def on_language_selected(call: CallbackQuery):
    cache = get_cache(call.from_user.id)
    args = call.data.split('_')
    if cache.get("sender") is None:
        sender = get_sender_data(chat_id=call.message.chat.id, address=args[2])[0]
    else:
        sender = get_sender_data(id=cache.get('sender'))[0]
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(call.message.chat.id)]
    sender['language'] = args[1]
    sender['collection_address'] = args[2]
    sender['telegram_id'] = call.message.chat.id
    sender['telegram_user'] = call.from_user.id
    sender_id = set_sender_data(sender)
    enter_cache(user_id=call.from_user.id, keys={'sender': sender_id})
    if call.from_user.id in can_setup:
        await try_to_edit(translate[sender['language']]["setup"][0], call.message.chat.id, call.message.message_id)
    else:
        await call.answer(translate[sender['language']]["setup"][1], show_alert=True)
        
@dp.message_handler(lambda message: message.reply_to_message and any(translate[x]["setup"][0] for x in translate))
async def handle_reply(message: types.Message):
    cache = get_cache(message.from_user.id)
    sender = get_sender_data(id=cache.get('sender'))[0]
    user = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    if user.status != "creator" and user.status != "administrator":
        await message.reply(translate[sender['language']]["setup"][1])
        return
    if address_converter(message.text):
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=message.text)
            sender["name"] = collection.name
            sender['telegram_user'] = message.from_user.id
            sender['collection_address'] = message.text
            set_sender_data(sender)
            await message.reply(translate[sender['language']]["setup"][2])
    else:
        await message.reply(translate[sender['language']]["setup"][3])
    
@dp.message_handler(commands=["nftlist"])
async def list_notifications(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        senders = get_sender_data(chat_id=message.chat.id)
        text = f"<b>{translate[return_chat_language(message.chat.id)]['settings'][0]}</b>\n"
        keyboard = InlineKeyboardMarkup(row_width=1)
        for sender in senders:
            keyboard.add(InlineKeyboardButton(f"{short_address(sender['collection_address'])}", 
                                                callback_data=f"setup_{sender['collection_address']}"))
        await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
        
        try :
            await message.delete()
        except Exception as e:
            logger.error(f"Failed to delete the message: {e}")

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
            await try_to_edit(text=text, chat_id=query.message.chat.id, message_id=query.message.message_id, keyboard=keyboard)      

@dp.message_handler(commands=["nftadd"])
async def add_notification(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        args = message.text.split()[1:]
        senders = get_sender_data(chat_id=message.chat.id)
        addresses = [address_converter(sender['collection_address']) for sender in senders]
        if len(args) != 1:
            await new_message(text="Input command again", chat_id=message.chat.id)

        if address_converter(args[0]) in addresses:
            await new_message(text="Collection already added", chat_id=message.chat.id)
            return
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for code in translate:
            b = InlineKeyboardButton(text=translate[code]['Name'], 
                                    callback_data=f"addnotif_{code}_{args[0]}")
            keyboard.add(b)
        text = f"Choose language for notification on collection <b>{args[0]}</b>"
        await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
    else:
        args = message.text.split()[1:]
        text = f"Collection {args[0]} not found, input command again"
        await new_message(text="Input command again", chat_id=message.chat.id)
        await try_to_delete(message.chat.id, message.message_id)

@dp.callback_query_handler(lambda call: call.data.startswith('addnotif_'))
async def add_notification_call(query: types.CallbackQuery):
    args = query.data.split('_')[1:]
    await query.answer(f"Processing to add and verificate the collection ({args[1]}), please wait a few seconds...", show_alert=True)
    async with aiohttp.ClientSession() as session:
        collection = await get_collection_info(session=session, collection_address=args[1])
    if collection and address_converter(collection.address) == address_converter(args[1]):
        sender = get_sender_data(chat_id=query.message.chat.id, collection_address=args[1])[0]
        sender['collection_address'] = args[1]
        sender['telegram_id'] = query.message.chat.id
        sender['telegram_user'] = query.from_user.id
        sender['name'] = collection.name
        sender['language'] = args[0]
        set_sender_data(sender)
        text = f"Notification for collection <code>{args[1]}</code> added"
        await new_message(text=text, chat_id=query.message.chat.id)
        await add_notification(query.message)
    else:
        text = f"Collection <code>{args[1]}</code> not found"
        await new_message(text=text, chat_id=query.message.chat.id)
        
@dp.message_handler(commands=["nftdel"])
async def delete_notification(message: types.Message):
    can_setup = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
    if not(message.chat.type == types.ChatType.PRIVATE or message.from_user.id in can_setup):
        args = message.text.split()[1:]
        senders = get_sender_data(chat_id=message.chat.id)
        addresses = [sender['collection_address'] for sender in senders]
        if len(args) != 1:
            await new_message(text="Input command again", chat_id=message.chat.id)
            return
        if args[0] not in addresses:
            text = f"Collection <code>{args[0]}</code> not found"
            await new_message(text=text, chat_id=message.chat.id)
            return
        delete_senders_data(args[0], message.chat.id)
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=args[0])
            text = f"Notification for collection <code>\"{collection.name}\"</code> deleted"
            await new_message(text=text, chat_id=message.chat.id)

    await try_to_delete(message.chat.id, message.message_id)
    




        


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
        link = 'https://getgems.io/'
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
    logger.info(f"\n\n----- Start of new session, version: {app_version}, now timestamp: {get_last_time()}, date: {number_to_date(get_last_time())} -----")
    await prepare()
    asyncio.create_task(run_periodically(300, enter_cmc_price))
    asyncio.create_task(run_periodically(5, history_notify))

    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
