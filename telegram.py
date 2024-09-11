import asyncio
import re
import json
import aiofiles
import traceback
import random
import time

from date import now, number_to_date
from database import (fetch_config_data, get_last_time, get_ad, enter_last_time, enter_price, update_senders_data, 
                      return_chat_language, delete_senders_data,  get_logger, enter_cache, get_cache, get_sender_data, 
                      set_sender_data, clear_cache, clear_bad_senders, get_topic, set_topic)
from getgems import (
    get_new_history, get_nft_info, get_collection_info, address_converter, short_address,
    HistoryItem, HistoryType, ContentType, NftItem, MarketplaceType, AddressType
)
from responce import coinmarketcap_price
from proxy import prepare

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramNotFound, TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter


logger = get_logger()

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
local = config.pop('local')
translate = config.pop('translate')
snippet = config.pop('snippets')
false_inline = config.pop('false_inline')
notify_settings = config.pop('notify_setup')
DEFAULT_PARSE_MODE = "HTML"
DISABLE_WEB_PAGE_PREVIEW = True

# Bot setup
config = fetch_config_data()
bot = Bot(config['bot_api'])
bot_info = asyncio.get_event_loop().run_until_complete(bot.get_me())
invite = f"https://t.me/{bot_info.username}?startgroup=true&admin=post_messages+edit_messages+delete_messages"
dp = Dispatcher()

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
    return user.status in ['creator', 'administrator'] and not user.is_anonymous

async def can_setup_notif(message:types.Message, sender_id:int) -> bool:
    sender = get_sender_data(id=sender_id)[0]
    can_stp = await can_setup_bot(message)
    return can_stp or (sender['telegram_user'] == message.from_user.id and sender['telegram_id'] == message.chat.id)

def to_bot_or_not(message:types.Message, command:str = None) -> bool:
    if not command:
        command = message.text.split()[0].split('/')[1].split('@')[0]
        if not command:
            return None
    return message.text.startswith(f'/{command}@{bot_info.username}') \
        or message.text.startswith(f'/{command}') and '@' not in message.text

def is_command(message:types.Message, command:str) -> bool:
    is_this_command = message.text.startswith(f'/{command}')
    if not is_this_command:
        return False
    return to_bot_or_not(message)

def find_topic_context(message:types.Message):
    r = message.reply_to_message
    return r.forum_topic_edited or r.forum_topic_created

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
    except (TelegramNotFound, TelegramForbiddenError):
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
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard, parse_mode=DEFAULT_PARSE_MODE)
        return True
    except (TelegramNotFound, TelegramForbiddenError):
        return False
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return
    
async def new_message(text: str, chat_id: int, thread_id: int = -1 ,keyboard: InlineKeyboardMarkup = None, file_type: FilesType = FilesType.NONE, file = None) -> types.Message:
    async def send():
        if file_type == FilesType.IMAGE:
            return await bot.send_photo(caption=html_back_escape(text), 
                                         chat_id=chat_id,
                                         reply_markup=keyboard, 
                                         photo=file,
                                         message_thread_id=thread_id,
                                         parse_mode=DEFAULT_PARSE_MODE)
        elif file_type == FilesType.VIDEO:
            return await bot.send_video(caption=html_back_escape(text), 
                                         chat_id=chat_id, 
                                         reply_markup=keyboard, 
                                         video=file,
                                         message_thread_id=thread_id,
                                         parse_mode=DEFAULT_PARSE_MODE)
        elif file_type == FilesType.DOCUMENT:
            return await bot.send_document(caption=html_back_escape(text), 
                                           chat_id=chat_id,
                                           reply_markup=keyboard, 
                                           document=file,
                                           message_thread_id=thread_id,
                                           parse_mode=DEFAULT_PARSE_MODE)
        elif file_type == FilesType.NONE:
            return await bot.send_message(text=html_back_escape(text), 
                                          chat_id=chat_id,
                                          reply_markup=keyboard,
                                          message_thread_id=thread_id,
                                          parse_mode=DEFAULT_PARSE_MODE,
                                          disable_web_page_preview=DISABLE_WEB_PAGE_PREVIEW)        
    
    thread_id = None if thread_id == -1 else thread_id
    try:
        return await send()
    except TelegramForbiddenError as e:
        logger.warning("Bot was blocked by user ({user_id}): {e}".format(user_id=chat_id, e=e))
    except TelegramNotFound as e:
        logger.warning("Chat ({user_id}) not found: {e}".format(user_id=chat_id, e=e))
    except TelegramRetryAfter as e:
        asyncio.sleep(int(e.retry_after) + 1 + random.random())
        return await send()
    except TelegramAPIError as e:
        logger.warning("Some error occured in chat ({user_id}): {e}".format(user_id=chat_id, e=e))
    except Exception as e:
        error_text =  str(e)
        logger.error(f'Error sending message in chat {chat_id}: {error_text}')
        return

@dp.callback_query(lambda c: c.data == 'delete_message')
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
async def send_notify(nft: NftItem, chat_id: int, lang: str, topic_id: int = -1, tz: int = 0, retries=3):
    if nft.sale is None:
        logger.error(f"Sale is None: {nft}")
        return -1

    bot_info = await bot.get_me()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    getgems_text = f"{translate[lang]['tg_util'][0]} Getgems" if nft.marketplace == MarketplaceType.Getgems or "getgems" in nft.sale.link else f"{translate[lang]['tg_util'][0]} {extract_main_domain(url=nft.sale.link)}"
    getgems_button = InlineKeyboardButton(text=getgems_text, url=nft.sale.link)
    tonviewer_button = InlineKeyboardButton(text=f"{translate[lang]['tg_util'][1]} TonViewer", url=f"https://tonviever.com/{nft.address}")
    keyboard.inline_keyboard.append([getgems_button, tonviewer_button])

    collection_button = InlineKeyboardButton(text=f"{translate[lang]['tg_util'][2]} Getgems", url=nft.collection.get_url())
    keyboard.inline_keyboard.append([collection_button])

    ad = get_ad()
    if ad and notify_settings['ads']:
        curr_ad = ad[random.randint(0, len(ad) - 1)]
        if curr_ad['link'] == '{bot.link}':
            curr_ad['link'] = 'https://t.me/' + bot_info.username
            curr_ad['name'] = translate[lang]['tg_util'][4]
        else:
            curr_ad['name'] = f"AD: {curr_ad['name']}"
        ad_button = InlineKeyboardButton(text=curr_ad['name'], url=curr_ad['link'])
        keyboard.inline_keyboard.append([ad_button])

    if notify_settings['setup']:
        setup_button = InlineKeyboardButton(text=f"{translate[lang]['tg_util'][3]}", url=invite)
        keyboard.inline_keyboard.append([setup_button])

    text = nft.notify_text(tz=tz, lang=lang)
    content = nft.get_content_url()
    _thread = get_topic(id=topic_id)

    for _ in range(retries + 1):
        try:
            if nft.content.type == ContentType.Image:
                photo = content if "https://" in content else nft.get_content_url(original=False)
                await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.IMAGE, file=photo, thread_id=_thread['thread_id'])
            elif nft.content.type == ContentType.Video:
                video = content if "https://" in content else nft.get_content_url(original=False)
                await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.VIDEO, file=video, thread_id=_thread['thread_id'])
            else:
                async with aiofiles.open(nft.content.original, 'rb') as photo:
                    await new_message(text=text, chat_id=chat_id, keyboard=keyboard, file_type=FilesType.DOCUMENT, file=photo, thread_id=_thread['thread_id'])
            return True
        except Exception as e:
            logger.error(e)
            await asyncio.sleep(1)
    return False

async def nft_history_notify(history_item: HistoryItem, chat_id: int, lang: str, topic_id: int = -1, tz: int = 0):
    try:
        nft = await get_nft_info(history_item)
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

        await send_notify(nft=nft, chat_id=chat_id, lang=lang, tz=tz, topic_id=topic_id)
        
    except Exception as e:
        logger.error(f"Error in nft_history_notify: {e}")

async def prepare_notify(first=10):
    count = 0
    history_items = []
    senders_data = get_sender_data()
    senders_data = [s for s in senders_data if all(s[k] is not None for k in s.keys())]
    logger.info("Start checking for new history data...")

    async def gather_history_for_sender(sender: dict) -> list[tuple]:
        cache = get_cache(sender['telegram_user'])
        lang = return_chat_language(sender['telegram_id'])
        try:
            chat = await bot.get_chat(sender['telegram_id'])
        except (TelegramNotFound, TelegramForbiddenError):
            delete_senders_data(chat_id=sender['telegram_id'])
            _thread = get_topic(id=sender['topic_id'])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=translate[lang]['tg_util'][3], url=invite)]])
            await new_message(text=f"You deleted me from the chat {snippet(sender['telegram_id'])}\nPlease let me back.", 
                              chat_id=sender['telegram_user'],
                              keyboard=keyboard, thread_id=_thread['thread_id'])
            return []
        except Exception as e:
            chat = None
            logger.error(f"Error in prepare_notify: {e}")
            
        if not chat or chat and chat.permissions and chat.permissions.can_send_messages is False:
            return []
        elif chat.permissions and cache.get(f'{sender["telegram_id"]}_error'):
            await bot.delete_message(chat_id=sender['telegram_user'], message_id=cache[f'{sender["telegram_id"]}_error'])
            cache.pop(f'{sender["telegram_id"]}_error', None)

        # Получаем историю для текущего отправителя
        history = await get_new_history(sender, config['ton_api'], first)
        
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
                        history_item=history,
                        chat_id=sender['telegram_id'],
                        lang=sender['language'],
                        tz=sender['timezone'],
                        topic_id=sender['topic_id']
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
    logger.info(f"Notification process ended, total notifications: {count}, now timestamp {get_last_time()} ({number_to_date(get_last_time())})")
    return count
        
 
 
 
   
# Setup functions
def language_keyboard(id: int = -1) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])  # You can set row_width as needed
    for language, details in translate.items():
        button_text = details.get("Name", "Unknown")
        callback_data = f'lang_{language}{"_" + str(id) if id > -1 else ""}'
        button = InlineKeyboardButton(text=button_text, callback_data=callback_data)
        keyboard.inline_keyboard.append([button])
    return keyboard

def quit_keyboard(chat_id:int, key: InlineKeyboardMarkup = None):
    lang = return_chat_language(chat_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[] if not key else key.inline_keyboard)
    keyboard.inline_keyboard.append([InlineKeyboardButton(text=translate[lang]["Close"], callback_data='delete_message')])
    return keyboard

async def is_bot_configured(message: types.Message):
    is_setup = True
    
    lang = return_chat_language(message.chat.id)
    text = translate[lang]['is_setup_complete'].split('\n')
    text[0] = snippet['bold'].format(text=text[0])
    text[1] = snippet['italic'].format(text=text[1])
    text = '\n\n'.join(text)
    key = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{translate[lang]['tg_util'][3]}", url=invite)]])
    keyboard = quit_keyboard(message.chat.id, key)
    
    if message.chat.type == 'private':
        await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard, thread_id=message.message_thread_id)
        return
    
    checker = await bot.get_chat_member(chat_id=message.chat.id, user_id=bot_info.id)
    
    # Проверяем статус бота (должен быть администратором или создателем)
    if checker.status not in ['creator', 'administrator']:
        is_setup = False
    else:
        chat = await bot.get_chat(chat_id=message.chat.id)

        # Проверяем конкретные права
        can_send = chat.permissions.can_send_messages if chat.permissions else False
        # can_edit = checker.can_edit_messages if checker else False
        can_delete = checker.can_delete_messages if checker else False
        is_setup = all([can_send, can_delete])
    
    if not is_setup:
        lang = return_chat_language(message.chat.id)
        keyboard = quit_keyboard(message.chat.id)
        await new_message(chat_id=message.chat.id, text=text, keyboard=keyboard, thread_id=message.message_thread_id)
        await new_message(chat_id=message.from_user.id, text=text, keyboard=keyboard, thread_id=message.message_thread_id)
    
    await try_to_delete(message.chat.id, message.message_id)
    return is_setup

@dp.message(lambda message: is_command(message, 'start'))
async def start_setup(message: types.Message):
    if not message.chat.type == 'private':
        await add_setup(message)
    else:
        await is_bot_configured(message)

@dp.message(lambda message: is_command(message, 'add_notification'))
async def add_setup(message: types.Message):
    can_setup = await can_setup_bot(message)
    is_configured = await is_bot_configured(message)
    await try_to_delete(message.chat.id, message.message_id)
    if not message.chat.type == 'private' and all([can_setup, is_configured]):
        logger.info(f"Bot added to a new chat: {message.chat.id}")
        senders = get_sender_data(chat_id=message.chat.id, thread_id=message.message_thread_id or -1, new = True)
        sender = senders[0]
        
        if message.chat.type == 'supergroup':
            topic_context = find_topic_context(message).name
            tid = set_topic(topic={'chat_id': message.chat.id, 'thread_id': message.message_thread_id or -1, 'name': topic_context})
            sender['topic_id'] = tid or -1
        else:
            sender['topic_id'] = -1
        
        sender['telegram_id'] = message.chat.id
        sender['telegram_user'] = message.from_user.id
        id = sender.get('id') or -1
        lang = return_chat_language(message.chat.id)
        setup_message = await new_message(chat_id=message.chat.id, text=translate[lang]['start_setup'], keyboard=language_keyboard(id), thread_id=message.message_thread_id)
        messid = setup_message.message_id if setup_message else -1

        set_sender_data(sender, id = id)
        enter_cache(user_id=message.chat.id, keys={'sender': int(sender['id']), 'setup':  message.message_id})
        logger.info(f"Setup message sent with ID: {messid}")
        
    elif not can_setup:
        lang = return_chat_language(message.chat.id)
        text = translate[lang]['is_setup_complete'].split('\n')
        text[0] = snippet['bold'].format(text=text[0])
        text[1] = snippet['italic'].format(text=text[1])
        text = '\n\n'.join(text)
        await new_message(chat_id=message.chat.id, text=text, keyboard=quit_keyboard(message.chat.id), thread_id=message.message_thread_id)
    
@dp.message(lambda message: is_command(message, 'list_notification'))
async def list_notifications(message: types.Message, delete = False):
    
    if not message.chat.type == 'private':
        senders = get_sender_data(chat_id=message.chat.id, thread_id=message.message_thread_id or -1)
    else:
        senders = get_sender_data(user_id=message.chat.id)
        
    lang = return_chat_language(message.chat.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    valid = 0
    for sender in senders:
        if all(sender.get(x) is not None for x in sender):
            valid += 1
            if message.chat.type == 'private':
                try:
                    _chat = await bot.get_chat(sender['telegram_id'])
                except:
                    _chat = None
            else:
                _chat = message.chat
            _topic = get_topic(sender['topic_id'])  
            
            if message.chat.type == 'private':
                # Для приватных чатов
                name = f'{_chat.full_name if _chat else "Chat ID: " + sender["telegram_id"]}' \
                    f', {("TID: " + sender["topic_id"] if not _topic else _topic["name"]) if _chat.type == "supergroup" else ""}'
            else:
                # Для остальных типов чатов
                name = short_address(sender['collection_address'])

            if not delete:
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{sender['name']} ({name})", callback_data=f"setup_{sender['id']}")])
            else:
                keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{sender['name']} ({name})", callback_data=f"delete_{sender['id']}")])
    if not (delete or message.chat.type == 'private'):
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=translate[lang]["Add"], callback_data='add_notification')])
    keyboard = quit_keyboard(message.chat.id, keyboard)
    text = snippet['bold'].format(text=(translate[lang]['settings'][10 if message.chat.type == 'private' else 0].format(count=valid) if not delete else translate[lang]['settings'][9]))
    await new_message(text=text, chat_id=message.chat.id, keyboard=keyboard, thread_id=message.message_thread_id)
    await try_to_delete(message.chat.id, message.message_id)

@dp.message(lambda message: is_command(message, 'delete_notification'))
async def delete_notification_command(message: types.Message):
    await try_to_delete(message.chat.id, message.message_id)
    await list_notifications(message, delete=True)

@dp.message(lambda message: is_command(message, 'help'))
async def help_note(message: types.Message):
    lang = return_chat_language(message.chat.id)
    keyboard = quit_keyboard(message.chat.id)
    await new_message(text=translate[lang]['help_note'], chat_id=message.chat.id, keyboard=keyboard, thread_id=message.message_thread_id)
    
@dp.callback_query(lambda call: call.data.startswith('lang_'))
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
        sender['telegram_user'] = call.from_user.id
        sender_id = set_sender_data(sender)
        enter_cache(user_id=call.message.chat.id, keys={'sender': int(sender_id), 'setup':  call.message.message_id})
        await try_to_edit(translate[sender['language']]["setup"][0], call.message.chat.id, call.message.message_id)
    else:
        await call.answer(translate[sender['language']]["setup"][1], show_alert=True)

@dp.callback_query(lambda query: query.data.startswith('setup_'))
async def settings(query: types.CallbackQuery):
    sender = get_sender_data(id=int(query.data.split('_')[1]))[0]
    can_setup = await can_setup_notif(query.message, sender['id'])
    if can_setup:
        lang = return_chat_language(query.message.chat.id)
        address = sender['collection_address']
        text = f"<b>{translate[lang]['settings'][1]}</b>\n\n"
        _chat = await bot.get_chat(sender['telegram_id'])
        collection = await get_collection_info(collection_address=address)
        if collection and address_converter(collection.address) == address_converter(address):
            text += f"{snippet['bold'].format(text=translate[lang]['settings'][2])}: {collection.name}\n"
            text += f"{snippet['bold'].format(text=translate[lang]['settings'][3])}: {snippet['code'].format(text=collection.address)}\n"
            text += f"{snippet['bold'].format(text=translate[lang]['settings'][4])}: {collection.owner.link_user_text()}\n\n"
            text += f"{snippet['bold'].format(text=translate[lang]['settings'][5])}: {collection.description}\n\n"
            
            text += snippet['bold'].format(text=translate[lang]['settings'][11].format(text=f'{_chat.full_name} ({snippet["code"].format(text=_chat.id)})')) + "\n"
            text += f"{snippet['bold'].format(text=translate[lang]['settings'][12]).format(text=get_topic(id=sender['topic_id'])['name']) if sender['topic_id'] != -1 else '#general'}\n" if _chat.type == 'supergroup' else ''
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[# InlineKeyboardButton(text=f"{translate[lang]['settings'][6]}", callback_data=f"edit_{int(query.data.split('_')[1])}"),
                                                InlineKeyboardButton(text=f"{translate[lang]['settings'][7]}", callback_data=f"delete_{int(query.data.split('_')[1])}")]])
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{translate[lang]['settings'][8]}", callback_data="list_notification")])
            await try_to_edit(text=text, chat_id=query.message.chat.id, message_id=query.message.message_id, keyboard=keyboard)      
            
@dp.callback_query(lambda c: c.data.startswith('delete_'))
async def delete_notification(callback: types.CallbackQuery):
    message = callback.message
    args = callback.data.split('_')[1:]
    sender = get_sender_data(id=int(args[0]))[0]
    can_setup = await can_setup_notif(message, int(args[0]))
    if not message.chat.type == 'private' and can_setup:
        delete_senders_data(id = args[0])
        text = f"{translate[return_chat_language(message.chat.id)]['delete']}: {snippet['bold'].format(text=sender['name'])}\n({snippet['code'].format(text=args[0])})"
        await new_message(text=text, chat_id=message.chat.id, keyboard=quit_keyboard(message.chat.id), thread_id=message.message_thread_id)

    await try_to_delete(message.chat.id, message.message_id)
        
@dp.message(lambda message: message.reply_to_message and any(translate[x]["setup"][0] in message.reply_to_message.text for x in translate if message.reply_to_message.text))
async def handle_reply(message: types.Message):
    cache = get_cache(message.chat.id)
    sender = get_sender_data(id=cache.get('sender'))[0]
    lang = return_chat_language(message.chat.id)
    can_setup = await can_setup_notif(message, sender['id'])
    if not can_setup or message.reply_to_message.message_id != cache.get('setup'):
        await message.reply(translate[lang]["setup"][1])
        return
    if address_converter(message.text):
        collection = await get_collection_info(collection_address=message.text)
        sender["name"] = collection.name
        sender['telegram_user'] = message.from_user.id
        sender['collection_address'] = message.text
        if not get_sender_data(address=message.text, chat_id=message.chat.id, thread_id=message.message_thread_id or -1):
            set_sender_data(sender, id = cache.get('sender'))
            await message.reply_to_message.reply(translate[lang]["setup"][2], reply_markup=quit_keyboard(message.chat.id))
            clear_cache(message.chat.id)
        else:
            await message.reply_to_message.reply(translate[lang]["setup"][4], reply_markup=quit_keyboard(message.chat.id))
            await try_to_delete(message.chat.id, cache.get('setup'))
    else:
        await message.reply_to_message.reply(translate[lang]["setup"][3])
    await try_to_delete(message.chat.id, cache.get('setup'))
    

@dp.callback_query(lambda c: c.data.startswith('list_notification'))
async def list_notifications_callback(callback: types.CallbackQuery):
    message = callback.message
    await list_notifications(message)

@dp.callback_query(lambda c: c.data.startswith('add_notification'))
async def add_notifications_callback(callback: types.CallbackQuery):
    message = callback.message
    await add_setup(message)

# just inline
@dp.inline_query()
async def inline_link_preview(query: types.InlineQuery):
    address = address_converter(query.query, format=AddressType.Bouncable)
    if not address:
        return
    
    nft = asyncio.create_task(get_nft_info(address))
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
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[[inline_button]])
        
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
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[[inline_button]])
        
        result = types.InlineQueryResultPhoto(
            id='true_inline',
            photo_url=thumb,
            thumb_url=thumb,
            title=title,
            description=desc,
            reply_markup=inline_keyboard,
            input_message_content=types.InputTextMessageContent(
                message_text=nft.notify_text(),
                disable_web_page_preview=True,
            )
        )    
        
    await query.answer([result], cache_time=1)
    
    
    
# just main
async def on_startup():
    logger.info(f"\n\n----- Start of new session, version: {app_version}, now timestamp: {get_last_time()}, date: {number_to_date(get_last_time())} -----")
    await prepare()
    clear_bad_senders()
    asyncio.create_task(run_periodically(300, enter_cmc_price))
    asyncio.create_task(run_periodically(notify_settings['delay'], prepare_notify))
    
async def main():
    await on_startup()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    while True:
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main())
        except (KeyboardInterrupt, SystemExit):
            break
        finally:
            logger.warning("Telegram bot stopped! Retry in 30 sec")
            time.sleep(30)
            loop.close()
