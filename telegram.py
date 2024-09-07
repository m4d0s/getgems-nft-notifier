import asyncio
import re
import json
import aiofiles
import traceback
import aiohttp
import random

from date import now, number_to_date
from database import (fetch_config_data, get_last_time, get_ad, enter_last_time, enter_price, update_senders_data, 
                      return_chat_language, delete_senders_data,  get_logger, enter_cache, get_cache, get_sender_data, 
                      set_sender_data, clear_cache, clear_bad_senders)
from getgems import (
    get_new_history, get_nft_info, get_collection_info, address_converter, short_address,
    HistoryItem, HistoryType, ContentType, NftItem, MarketplaceType, AddressType
)
from responce import coinmarketcap_price
from proxy import prepare

from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.exceptions import (MessageNotModified, MessageToDeleteNotFound, ChatNotFound, BotBlocked, RetryAfter,
                                      MessageToEditNotFound, MessageCantBeDeleted, MessageCantBeEdited, UserDeactivated)


logger = get_logger()

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
local = config.pop('local')
translate = config.pop('translate')
snippet = config.pop('snippets')
false_inline = config.pop('false_inline')


# Bot setup
config = fetch_config_data()
bot = Bot(config['bot_api'])
bot_info = asyncio.get_event_loop().run_until_complete(bot.get_me())
dp = Dispatcher(bot)

elligible = [HistoryType.Sold, HistoryType.PutUpForSale, HistoryType.PutUpForAuction]
price_ids = [11419, 28850, 825, 1027, 1]
app_version = "0.9a"

class FilesType:
    NONE = 0
    IMAGE = 1
    VIDEO = 2
    DOCUMENT = 3



# Helpful functions
async def can_setup_bot(message:types.Message) -> bool:
    user = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    return user.status in ['creator', 'administrator']

async def can_setup_notif(message:types.Message, sender_id:int) -> bool:
    sender = get_sender_data(id=sender_id)[0]
    can_stp = await can_setup_bot(message)
    return can_stp or (sender['telegram_user'] == message.from_user.id and sender['telegram_id'] == message.chat.id)

def to_bot_or_not(message:types.Message, command:str = None) -> bool:
    if not command:
        command = message.get_command(pure=True)
        if not command:
            return None
    return message.text.startswith(f'/{command}@{bot_info.username}') \
        or message.text == f'/{command}' and '@' not in message.text

def is_command(message:types.Message, command:str) -> bool:
    is_this_command = message.text.startswith(f'/{command}')
    is_this_to_bot = to_bot_or_not(message)
    return all([is_this_command, is_this_to_bot])

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
    async def send():
        if file_type == FilesType.IMAGE:
            return await bot.send_photo(caption=html_back_escape(text), 
                                         chat_id=chat_id, 
                                         parse_mode=parse_mode, 
                                         reply_markup=keyboard, 
                                         photo=file)
        elif file_type == FilesType.VIDEO:
            return await bot.send_video(caption=html_back_escape(text), 
                                         chat_id=chat_id, 
                                         parse_mode=parse_mode, 
                                         reply_markup=keyboard, 
                                         video=file)
        elif file_type == FilesType.DOCUMENT:
            return await bot.send_document(caption=html_back_escape(text), 
                                           chat_id=chat_id, 
                                           parse_mode=parse_mode, 
                                           reply_markup=keyboard, 
                                           document=file)
        elif file_type == FilesType.NONE:
            return await bot.send_message(text=html_back_escape(text), 
                                          chat_id=chat_id, 
                                          parse_mode=parse_mode, 
                                          disable_web_page_preview=disable_preview, 
                                          reply_markup=keyboard)        
    
    try:
        await send()
    # except MessageIsTooLong:
    #     logger.warning('Message is too long to send in chat ' + str(chat_id))
    except UserDeactivated:
        logger.warning("User ({user_id}) deactivated".format(user_id=chat_id))
    except BotBlocked:
        logger.warning("Bot was blocked by user ({user_id})".format(user_id=chat_id))
    except ChatNotFound:
        logger.warning("Chat ({user_id}) not found".format(user_id=chat_id))
    except RetryAfter as e:
        asyncio.sleep(e.timeout + random.random())
        await send()
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
  
async def send_error_message(chat_id:int, message:str, e:Exception = None, only_dev:bool = False) -> types.Message:
    cache = await get_cache(chat_id) ##cache
    keyboard = quit_keyboard(chat_id)
    
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
    try:
        # Удаляем текущее сообщение
        await try_to_delete(call.message.chat.id, call.message.message_id)
        
        message = call.message
        
        # Проходим по цепочке ответов
        while message.reply_to_message:
            message = message.reply_to_message
            await try_to_delete(message.chat.id, message.message_id)
    
    except Exception as e:
        # Логируем ошибку, если что-то пошло не так
        logger.error(f"Error deleting messages: {e}")





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
    senders_data = get_sender_data()
    senders_data = [s for s in senders_data if all(s[k] is not None for k in s.keys())]

    async def gather_history_for_sender(sender: dict) -> list[tuple]:
        cache = get_cache(sender['telegram_user'])
        try:
            chat = await bot.get_chat(sender['telegram_id'])
        except Exception as e:
            chat = None
            logger.error(f"Error in prepare_notify: {e}")
        
        if not chat:
            delete_senders_data(id=sender['id'])
            await new_message(text="You deleted me from the chat? Please let me back.", chat_id=sender['telegram_user'])
            return []
        elif chat.permissions and chat.permissions.can_send_messages is False:
            if not cache.get(f'{sender["telegram_id"]}_error'):
                MESS = await new_message(
                    text="You haven't given me permission to send messages.",
                    chat_id=sender['telegram_user'],
                    keyboard=quit_keyboard(sender['telegram_id'])
                )
                cache[f'{sender["telegram_id"]}_error'] = MESS.message_id
            return []
        elif chat.permissions and cache.get(f'{sender["telegram_id"]}_error'):
            await bot.delete_message(chat_id=sender['telegram_user'], message_id=cache[f'{sender["telegram_id"]}_error'])
            del cache[f'{sender["telegram_id"]}_error']

        # Получаем историю для текущего отправителя
        history = await get_new_history(session, sender, config['ton_api'], first)
        
        # Возвращаем историю для обработки
        return [(h, sender) for h in history]

    # Собираем результаты всех тасков
    tasks = [gather_history_for_sender(sender) for sender in senders_data]
    results = await asyncio.gather(*tasks)

    # Объединяем все элементы истории
    for result in results:
        history_items.extend(result)

    async def process_history_item(history_item: tuple, semaphore: asyncio.Semaphore) -> None:
        nonlocal count
        async with semaphore:  # Ограничение числа одновременных задач
            history, sender = history_item

            if history.type in elligible:
                if history.time == 0:
                    sender['last_time'] = now()  # Обновляем напрямую
                else:
                    await nft_history_notify(
                        session=session,
                        history_item=history,
                        chat_id=sender['telegram_id'],
                        lang=sender['language'],
                        tz=sender['timezone']
                    )
                    count += 1
                    sender['last_time'] = history.time  # Обновляем напрямую

    # Создаем семафор для ограничения параллельных задач
    semaphore = asyncio.Semaphore(10)  # Ограничиваем до 10 одновременных задач, можно изменить

    # Сортируем историю
    sorted_history_items = sorted(history_items, key=lambda x: int(x[0].time) + x[0].type.value, reverse=True)

    # Обрабатываем историю с использованием семафора
    tasks = [process_history_item(item, semaphore) for item in sorted_history_items]
    await asyncio.gather(*tasks)

    # Обновляем данные отправителей
    update_senders_data(senders_data)
    enter_last_time()

    return count

async def history_notify(counter=0):
    async with aiohttp.ClientSession() as session:
        logger.info("Start checking for new history data...")
        count = await prepare_notify(session)
        logger.info(f"Notification process ended, total notifications: {count}, now timestamp {get_last_time()} ({number_to_date(get_last_time())})")
 
 
 
 
        
# Setup functions
def language_keyboard(id:int = -1):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for language in translate:
        keyboard.add(InlineKeyboardButton(translate[language]["Name"], callback_data=f'lang_{language}{"_" + str(id) if id > -1 else ""}'))
    return keyboard

def quit_keyboard(chat_id:int):
    lang = return_chat_language(chat_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(translate[lang]["Close"], callback_data='delete_message'))
    return keyboard

@dp.message_handler(lambda message: is_command(message, 'start'))
@dp.message_handler(lambda message: is_command(message, 'add_notification'))
async def start_setup(message: types.Message):
    can_setup = await can_setup_bot(message)
    await try_to_delete(message.chat.id, message.message_id)
    if not message.chat.type == types.ChatType.PRIVATE and can_setup:
        logger.info(f"Bot added to a new chat: {message.chat.id}")
        senders = get_sender_data(chat_id=message.chat.id, new = True)
        sender = senders[0]
        sender['telegram_id'] = message.chat.id
        sender['telegram_user'] = message.from_user.id
        id = sender.get('id') or -1
        lang = return_chat_language(message.chat.id)
        setup_message = await new_message (chat_id=message.chat.id, text=translate[lang]['start_setup'], keyboard=language_keyboard(id))
        messid = setup_message.message_id

        enter_cache(message.chat.id, {"setup": messid, 'sender': id})
        logger.info(f"Setup message sent with ID: {messid}")
    
@dp.message_handler(lambda message: is_command(message, 'list_notification'))
async def list_notifications(message: types.Message, delete = False):
    senders = get_sender_data(chat_id=message.chat.id)
    if not message.chat.type == types.ChatType.PRIVATE:
        lang = return_chat_language(message.chat.id)
        keyboard = InlineKeyboardMarkup()
        valid = 0
        for sender in senders:
            if all(sender.get(x) is not None for x in sender):
                valid += 1
                if not delete:
                    keyboard.add(InlineKeyboardButton(f"{sender['name']} ({short_address(sender['collection_address'])})", callback_data=f"setup_{sender['id']}"))
                else:
                    keyboard.add(InlineKeyboardButton(f"{sender['name']} ({short_address(sender['collection_address'])})", callback_data=f"delete_{sender['id']}"))
        if not delete:
            keyboard.add(InlineKeyboardButton(translate[lang]["Close"], callback_data='delete_message'),
                        InlineKeyboardButton(translate[lang]["Add"], callback_data='add_notification'))
        else:
            keyboard.add(InlineKeyboardButton(translate[lang]["Close"], callback_data='delete_message'))
        text = snippet['bold'].format(text=(translate[lang]['settings'][0].format(count=valid) if not delete else translate[lang]['settings'][9]))
        await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard)
        await try_to_delete(message.chat.id, message.message_id)

@dp.message_handler(lambda message: is_command(message, 'delete_notification'))
async def delete_notification_command(message: types.Message):
    await try_to_delete(message.chat.id, message.message_id)
    await list_notifications(message, delete=True)

@dp.message_handler(lambda message: is_command(message, 'help'))
async def help_note(message: types.Message):
    lang = return_chat_language(message.chat.id)
    keyboard = quit_keyboard(message.chat.id)
    await new_message(text=translate[lang]['help_note'], chat_id=message.chat.id, keyboard=keyboard)
    
@dp.callback_query_handler(lambda call: call.data.startswith('lang_'))
async def on_language_selected(call: CallbackQuery):
    can_setup = await can_setup_notif(call.message, int(call.data.split('_')[2]))
    if can_setup:
        cache = get_cache(call.from_user.id)
        args = call.data.split('_')
        if cache.get("sender") is None and len(args) > 2:
            sender = get_sender_data(id=int(args[2]))[0]
        else:
            sender = get_sender_data(id=cache.get('sender'))[0]
        sender['language'] = args[1]
        sender['telegram_id'] = call.message.chat.id
        sender['telegram_user'] = call.from_user.id
        sender_id = set_sender_data(sender)
        enter_cache(user_id=call.message.chat.id, keys={'sender': int(sender_id), 'setup':  call.message.message_id})
        await try_to_edit(translate[sender['language']]["setup"][0], call.message.chat.id, call.message.message_id)
    else:
        await call.answer(translate[sender['language']]["setup"][1], show_alert=True)

@dp.callback_query_handler(lambda query: query.data.startswith('setup_'))
async def settings(query: types.CallbackQuery):
    sender = get_sender_data(id=int(query.data.split('_')[1]))[0]
    can_setup = await can_setup_notif(query.message, sender['id'])
    if can_setup:
        address = sender['collection_address']
        text = f"<b>{translate[return_chat_language(query.message.chat.id)]['settings'][1]}</b>\n\n"
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=address)
        if collection and address_converter(collection.address) == address_converter(address):
            text += f"{snippet['bold'].format(text=translate[return_chat_language(query.message.chat.id)]['settings'][2])}: {collection.name}\n"
            text += f"{snippet['bold'].format(text=translate[return_chat_language(query.message.chat.id)]['settings'][3])}: {snippet['code'].format(text=collection.address)}\n"
            text += f"{snippet['bold'].format(text=translate[return_chat_language(query.message.chat.id)]['settings'][4])}: {collection.owner.link_user_text()}\n\n"
            text += f"{snippet['bold'].format(text=translate[return_chat_language(query.message.chat.id)]['settings'][5])}: {collection.description}\n"
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                # InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][6]}", callback_data=f"edit_{int(query.data.split('_')[1])}"),
                InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][7]}", callback_data=f"delete_{int(query.data.split('_')[1])}")
                )
            keyboard.add(InlineKeyboardButton(f"{translate[return_chat_language(query.message.chat.id)]['settings'][8]}", callback_data="list_notification"))
            await try_to_edit(text=text, chat_id=query.message.chat.id, message_id=query.message.message_id, keyboard=keyboard)      
            
@dp.callback_query_handler(lambda c: c.data.startswith('delete_'))
async def delete_notification(callback: types.CallbackQuery):
    message = callback.message
    args = callback.data.split('_')[1:]
    sender = get_sender_data(id=int(args[0]))[0]
    can_setup = await can_setup_notif(message, int(args[0]))
    if not message.chat.type == types.ChatType.PRIVATE and can_setup:
        delete_senders_data(id = args[0])
        text = f"{translate[return_chat_language(message.chat.id)]['delete']}: {snippet['bold'].format(text=sender['name'])}\n({snippet['code'].format(text=args[0])})"
        await new_message(text=text, chat_id=message.chat.id, keyboard=quit_keyboard(message.chat.id))

    await try_to_delete(message.chat.id, message.message_id)
        
@dp.message_handler(lambda message: message.reply_to_message and any(translate[x]["setup"][0] in message.reply_to_message.text for x in translate))
async def handle_reply(message: types.Message):
    cache = get_cache(message.chat.id)
    sender = get_sender_data(id=cache.get('sender'))[0]
    lang = return_chat_language(message.chat.id)
    can_setup = await can_setup_notif(message, sender['id'])
    if not can_setup or message.reply_to_message.message_id != cache.get('setup'):
        await message.reply(translate[lang]["setup"][1])
        return
    if address_converter(message.text):
        async with aiohttp.ClientSession() as session:
            collection = await get_collection_info(session=session, collection_address=message.text)
            sender["name"] = collection.name
            sender['telegram_user'] = message.from_user.id
            sender['collection_address'] = message.text
            if not get_sender_data(address=message.text, chat_id=message.chat.id):
                set_sender_data(sender, id = cache.get('sender'))
                await message.reply(translate[lang]["setup"][2], reply_markup=quit_keyboard(message.chat.id))
                clear_cache(message.chat.id)
            else:
                await message.reply(translate[lang]["setup"][4], reply_markup=quit_keyboard(message.chat.id))
                await try_to_delete(message.chat.id, cache.get('setup'))
    else:
        await message.reply(translate[lang]["setup"][3])

@dp.callback_query_handler(lambda c: c.data.startswith('list_notification'))
async def list_notifications_callback(callback: types.CallbackQuery):
    message = callback.message
    await list_notifications(message)

@dp.callback_query_handler(lambda c: c.data.startswith('add_notification'))
async def add_notifications_callback(callback: types.CallbackQuery):
    message = callback.message
    await start_setup(message)

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
        link = false_inline['link']
        title = false_inline['title']
        desc = false_inline['desc']
        thumb = false_inline['thumb']
        
        inline_button = InlineKeyboardButton(text="Getgems", url=link)
        inline_keyboard = InlineKeyboardMarkup().add(inline_button)
        
        result = types.InlineQuery
    
        result = types.InlineQueryResultArticle(
                id='false_inline',
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
            id='true_inline',
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
    # clear_bad_senders()
    asyncio.create_task(run_periodically(300, enter_cmc_price))
    asyncio.create_task(run_periodically(5, history_notify))

    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
