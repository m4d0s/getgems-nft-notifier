import asyncio
import logging
import aiogram
import re
from logging import log

from getgems import HistoryItem, HistoryType, ContentType, NftItem, get_nft_info, get_collection_info
from getgems import SocialLinksItem, MarketplaceType
from date_util import number_to_date, log_format_time
from db_util import get_ad, fetch_config_data

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram import Bot

# from aiogram import Dispatcher, types
# from aiogram.filters import Command
# from aiogram.dispatcher import FSMContext
# from aiogram.types import Message, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.contrib.fsm_storage.memory import MemoryStorage
# from aiogram.dispatcher.filters.state import StatesGroup, State

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def send_notify(bot_token:str, data:NftItem, chat_id:int, chat_prefix = "-100", retries = 3):
    bot = Bot(bot_token)
    bot_info = await bot.get_me()

    # Создание клавиатуры с кнопками
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Добавление кнопок
    getgems_text = "Buy now on Getgems" if data.marketplace == MarketplaceType.Getgems or "getgems" in data.sale.link\
        else f"Buy now on {extract_main_domain(url=data.sale.link)}"
    getgems_button = InlineKeyboardButton(getgems_text, url=data.sale.link)
    tonviever_button = InlineKeyboardButton("Check on TonViewer", url=f"https://tonviever.com/{data.address}")
    keyboard.add(getgems_button, tonviever_button)
    
    ad = list(get_ad())
    if ad[2] == "" or ad[2] == "{bot.link}":
        ad[2] = f"https://t.me/{bot_info.username}"
    else:
        ad[1] = f"AD: {ad[1]}"
    ad_button = InlineKeyboardButton(ad[1], url=ad[2])
    keyboard.add(ad_button)
    
    collection_button = InlineKeyboardButton("Collection on Getgems", url=data.collection.get_url())
    keyboard.add(collection_button)
    
    setup_button = InlineKeyboardButton(text="Setup for your group/channel", url=f"https://t.me/{bot_info.username}?startgroup=true")
    keyboard.add(setup_button)
    
    text = data.notify_text()
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
                with open(data.content.original, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=f"-100{chat_id}",
                        photo=photo,
                        caption=text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard
                    )
            return 0
        except Exception as e:
            log(logging.FATAL, e)
            await asyncio.sleep(1)
            continue
 
def extract_main_domain(url: str):
    # Регулярное выражение для извлечения домена
    domain_regex = re.compile(r'^(?:http[s]?://)?(?:www\.)?([^:/\s]+)')
    match = domain_regex.search(url)
    if match:
      return match.group(1)
    return None 
        
async def nft_history_notify(history_item:HistoryItem, chat_id:int, TON_API:str, BOT_TOKEN:str):
    nft = await get_nft_info(history_item)

    if nft.history.type == HistoryType.Sold:
        log(logging.INFO, f'Sold: {nft.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    elif nft.history.type == HistoryType.PutUpForSale:
        log(logging.INFO, f'New NFT on sale: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    elif nft.history.type == HistoryType.PutUpForAuction:
        log(logging.INFO, f'New auction: {nft.collection.address} on collection {nft.collection.address} ({number_to_date(nft.history.time)})')
    else:
        log(logging.INFO, f"Another action happened: {history_item}")
        return
    await send_notify(BOT_TOKEN, data = nft, chat_id = chat_id)
    
# class Form(StatesGroup):
#     waiting_for_nft_address = State()

# bot_token = fetch_config_data()[0]
# bot = Bot(bot_token)
# storage = MemoryStorage()
# dp = Dispatcher(bot)

# # Команда /start
# @dp.message_handler(Command('start'))
# async def send_welcome(message: Message):
#     # Создаем клавиатуру
#     keyboard = InlineKeyboardMarkup()

#     # Добавляем кнопку для добавления бота в группу/канал
#     add_bot_button = InlineKeyboardButton(text="Добавить бота в группу/канал",
#                                           url=f"https://t.me/{bot.username}?startgroup=true")
#     keyboard.add(add_bot_button)

#     # Отправляем сообщение с клавиатурой
#     await message.reply("Привет! Нажми кнопку ниже, чтобы добавить меня в свою группу или канал.", reply_markup=keyboard)
    
# # Обработка нового чата
# @dp.message(content_types=types.ContentType.NEW_CHAT_MEMBERS)
# async def on_user_joined(message: types.Message):
#     for new_member in message.new_chat_members:
#         if new_member.id == bot.id:
#             # Бот добавлен в группу, назначаем права
#             try:
#                 await bot.promote_chat_member(
#                     chat_id=message.chat.id,
#                     user_id=bot.id,
#                     is_anonymous=False,
#                     can_manage_chat=True,
#                     can_delete_messages=True,
#                     can_manage_video_chats=True,
#                     can_restrict_members=True,
#                     can_promote_members=False,
#                     can_change_info=True,
#                     can_invite_users=True,
#                     can_post_messages=False,  # Только для каналов
#                     can_edit_messages=False  # Только для каналов
#                 )
#             except aiogram.exceptions.TelegramAPIError as e:
#                 print(f"Ошибка назначения прав администратора: {e}")

#             welcome_msg = await message.reply("Спасибо за добавление бота! Я получил необходимые права.\n\nПожалуйста, отправьте адрес NFT коллекции.")
#             # Устанавливаем состояние ожидания адреса NFT
#             await Form.waiting_for_nft_address.set()

#             # Сохраняем ID приветственного сообщения и пользователя, который добавил бота
#             async with storage.proxy() as data:
#                 data['welcome_msg_id'] = welcome_msg.message_id
#                 data['user_id'] = message.from_user.id

# # Обработка сообщения с адресом NFT коллекции
# @dp.message_handler(state=Form.waiting_for_nft_address, content_types=types.ContentType.TEXT)
# async def process_nft_address(message: Message, state: FSMContext):
#     async with state.proxy() as data:
#         user_id = data['user_id']
#         welcome_msg_id = data['welcome_msg_id']

#     chat_administrators = [admin.user.id for admin in await bot.get_chat_administrators(message.chat.id)]
#     delete_msg = [user_id, welcome_msg_id]
#     if message.from_user.id == user_id or message.from_user.id in chat_administrators:
#         nft_address = message.text
#         delete_msg.append(message.message_id)

#         # Проверяем адрес коллекции
#         nft_collection = await get_collection_info(nft_address)
#         while nft_collection is None:
#             ans = await message.reply("Неверный адрес NFT коллекции. Пожалуйста, проверьте и попробуйте снова.")
#             delete_msg.append(ans.message_id)

#         # Выводим в консоль ID группы и адрес NFT
#         print(f"Group ID: {message.chat.id}")
#         print(f"NFT Address: {nft_address}")

#         # Удаляем приветственное сообщение и сообщение с адресом NFT
#         for msg_id in delete_msg:
#             await bot.delete_message(chat_id=message.chat.id, message_id=msg_id)

#         # Отправляем сообщение об успешной настройке
#         success_msg = await message.reply(f"Адрес NFT коллекции '{nft_collection.name}' был успешно сохранен!")

#         # Удаляем сообщение об успешной настройке через 10 секунд
#         await asyncio.sleep(10)
#         await bot.delete_message(chat_id=message.chat.id, message_id=success_msg.message_id)

#         # Сбрасываем состояние
#         await state.finish()
#     else:
#         await message.reply("Только администраторы могут настраивать адрес NFT коллекции.")
    