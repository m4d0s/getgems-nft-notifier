import sqlite3
import logging
import json
import os
from date import now, log_format_time

db_path = json.load(open('getgems.json', 'r', encoding='utf-8'))["db_path"]

#logger
def get_logger(file_level=logging.INFO, base_level=logging.INFO):
    # Создаем логгер
    logger = logging.getLogger("logger")
    logger.setLevel(base_level)  # Устанавливаем базовый уровень логирования
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Проверяем, есть ли уже обработчики, и если да, удаляем их
    if logger.hasHandlers():
        logger.handlers.clear()

    # Создаем каталог для логов, если он не существует
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(f'{log_dir}/{log_format_time()}.log')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_lvl = logging.DEBUG
    console_handler.setLevel(console_lvl)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.debug("Logger setup sucessfull!\n\tBase log level: %s, Console log level: %s, File log level: %s", 
                 base_level, console_lvl, file_level)

    return logger

logger = get_logger()


#config
def fetch_config_data(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM config")
    config_data = cursor.fetchall()
    
    conn.close()
    
    config_data_list = {}
    for i in range(len(config_data)):
        config_data_list[config_data[i][0].lower()] = int(config_data[i][1]) if config_data[i][1].isdigit() else config_data[i][1]
        
    return config_data_list

def enter_last_time(db_path=db_path, timestamp = now()):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE config SET key = ? WHERE value = \"now\"", (timestamp,))
    conn.commit()
    
    conn.close()
    
def get_last_time(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT key FROM config WHERE value = \"now\"")
    last_time = cursor.fetchone()
    
    conn.close()
    
    return int(last_time[0])



#cache
def enter_cache(user_id:int, keys:dict, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for k, v in keys.items():
        v = str(v)
        cursor.execute("""
        INSERT OR REPLACE INTO cache (name, value, user_id) 
        VALUES (?, ?, ?)
        """, (k, v, user_id))
    conn.commit()
    
    conn.close()
    
def get_cache(user_id:int, db_path=db_path) -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM cache WHERE user_id = ?", (user_id,))
    cache = cursor.fetchall()
    
    conn.close()
    
    return {item[1]: item[2] for item in cache}




#price
def enter_price(value, db_path=db_path):
    if value is None:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for k, v in value.items():
        cursor.execute("""
        INSERT OR REPLACE INTO price (id, value, name) 
        VALUES (?, ?, ?)
        """, (k, v[0], v[1]))
    conn.commit()
    
    conn.close()
    
def get_price(db_path=db_path, name="") -> dict:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM price")
    prices = cursor.fetchall()
    
    conn.close()
    
    return {item[1]: item[2] for item in prices}



#setup
def return_chat_language(id, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT language FROM senders WHERE telegram_id = ? ORDER BY last_time DESC", (id,))
    senders_data = cursor.fetchone()
    
    conn.close()
    
    return senders_data[0]

def is_setup_by_chat_id(id, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM senders WHERE telegram_id = ?", (id,))
    senders_data = cursor.fetchone()
    
    conn.close()
    
    return True if senders_data and all(item is not None for _, item in enumerate(senders_data)) else False





#ads
def get_ad(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM ads")
    ad = cursor.fetchall()
    
    conn.close()
    
    ad_list = [list(row) for row in ad]
    now_time = now()
    
    #id name link time start end approve
    for i in ad[1:]:
        if i[4] < now_time < i[5] and i[6] == 1:
            return i
    return ad_list[0]




#senders
def fetch_all_senders(db_path=db_path) -> list:
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM senders")
    senders_data = cursor.fetchall()
    
    conn.close()
    
    senders_data_list = [dict(zip([description[0] for description in cursor.description], row)) 
                         for row in senders_data]
    return senders_data_list


def get_sender_data(address:str = None, chat_id:int = None, id=None, db_path=db_path) -> list:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if all([item is None for item in [address, chat_id, id]]):
        return [{}]
    
    text = []
    if address:
        text.append(f"collection_address = \"{address}\"")
    if chat_id:
        text.append(f"telegram_id = \"{chat_id}\"")
    if id:
        text.append(f"id = \"{id}\"")
        
    cursor.execute(f"SELECT * FROM senders WHERE {' AND '.join(text)} ORDER BY last_time DESC")
    senders_data = cursor.fetchall()
    conn.close()
    
    senders_data_list = [dict(zip([description[0] for description in cursor.description], sender_data)) for sender_data in senders_data] if senders_data \
        else [{}]
    return senders_data_list

def update_senders_data(updated_senders_data:list, db_path=db_path) -> None:
    for send in updated_senders_data:
        set_sender_data(send, db_path)

def set_sender_data(sender: dict, db_path=db_path) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sender['last_time'] = now()
    
    # Выполняем замену или вставку
    cursor.execute(f"INSERT OR REPLACE INTO senders ({', '.join(sender.keys())}) VALUES ({', '.join(['?']*len(sender))})", (*sender.values(),))
    
    # Получаем id вставленной или обновленной записи
    cursor.execute(f"SELECT id FROM senders WHERE {'AND '.join(f'{key} = ?' for key in sender.keys())}", (*sender.values(),))
    row_id = cursor.fetchone()
    row_id = row_id[0] if row_id else None 
    
    conn.commit()
    conn.close()
    
    return row_id

    
def delete_senders_data(address, id, db_path=db_path) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM senders
        WHERE collection_address = ? AND telegram_id = ?
    ''', (address, id))
    conn.commit()
    
    conn.close()