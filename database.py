import sqlite3
import logging
import json
import os
from date import now, log_format_time

db_path = json.load(open('getgems.json', 'r', encoding='utf-8'))["db_path"]
translate_default = [t for t in json.load(open('getgems.json', 'r', encoding='utf-8'))["translate"]][0] or "en"

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
        v = str(v) if v is not None else None
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
    return_dict = {}
    for item in cache:
        i = None
        if item[2] is None:
            i = None
        elif item[2].replace('-', '').isdigit():
            i = int(item[2])
        return_dict[item[1]] = i
        
    return return_dict




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
    
def get_price(db_path=db_path) -> dict:
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
    
    return senders_data[0] or translate_default if senders_data else translate_default

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

def update_senders_data(updated_senders_data:list, db_path=db_path) -> None:
    for send in updated_senders_data:
        set_sender_data(send, db_path)

def get_sender_data(address: str = None, chat_id: int = None, id: int = None, db_path: str = db_path, new = False) -> list[dict]:
    query = "SELECT * FROM senders"
    conditions = []
    params = []
    empty_dict = None
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM senders LIMIT 1")
        empty_dict = {description[0]: None for description in cursor.description}
    empty_dict['last_time'] = now()
    empty_dict['timezone'] = 0
    
    if new:
        return [empty_dict]

    # Строим список условий и параметров
    if address:
        conditions.append("collection_address = ?")
        params.append(address)
    if chat_id:
        conditions.append("telegram_id = ?")
        params.append(chat_id)
    if id:
        conditions.append("id = ?")
        params.append(id)

    # Добавляем условия к запросу, если они есть
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    else:
        return [empty_dict]
    
    query += " ORDER BY last_time DESC"

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Выполняем запрос
            cursor.execute(query, params)
            senders_data = cursor.fetchall()

            # Создаем пустой словарь на случай отсутствия данных


            # Преобразуем результат запроса в список словарей
            senders_data_list = [
                dict(zip([description[0] for description in cursor.description], sender_data))
                for sender_data in senders_data
            ] if senders_data else [empty_dict]

            return senders_data_list

    except sqlite3.Error as e:
        logger.error(f"An error occurred: {e}")
        return [empty_dict]

def set_sender_data(sender: dict, db_path: str = db_path, tz: int = 0, id: int = None) -> int:
    sender['last_time'] = now()
    sender['timezone'] = tz
    
    # Удаляем id из словаря, если он есть
    id = id or sender.pop('id', -1)
    
    try:
        # Открываем соединение с базой данных и создаем курсор
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            if id:
                # Если id существует, выполняем UPDATE
                cursor.execute(
                    f"UPDATE senders SET {', '.join(f'{key} = ?' for key in sender.keys())} WHERE id = ?",
                    (*sender.values(), id)
                )
                conn.commit()
                return id
            else:
                # Вставляем новую запись, если id не указан
                cursor.execute(
                    f"INSERT INTO senders ({', '.join(sender.keys())}) VALUES ({', '.join(['?'] * len(sender))})",
                    (*sender.values(),)
                )
                conn.commit()

                # Получаем id вставленной записи
                cursor.execute("SELECT id FROM senders WHERE rowid = ?", (cursor.lastrowid,))
                row = cursor.fetchone()
                return row[0] if row else -1
    
    except sqlite3.Error as e:
        logger.error(f"An error occurred: {e}")
        return -1


def delete_senders_data(address: str = None, chat_id: int = None, id: int = None, db_path: str = db_path) -> None:
    # Ensure that at least one of the parameters is provided to avoid accidental mass deletion
    if not any([address, chat_id, id]):
        logger.error("At least one parameter (address, chat_id, id) must be provided.")
        return
    
    # Construct the query and the parameters
    conditions = []
    params = []
    query = "DELETE FROM senders"
    
    if address:
        conditions.append("collection_address = ?")
        params.append(address)
    if chat_id:
        conditions.append("telegram_id = ?")
        params.append(chat_id)
    if id:
        conditions.append("id = ?")
        params.append(id)

    # Only add WHERE clause if there are conditions
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # Use context managers for better resource handling
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
    except sqlite3.Error as e:
        # Log or raise error for further handling
        logger.error(f"Database error occurred: {e}")
