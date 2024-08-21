import sqlite3
import logging
import json
from date import now, log_format_time

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

db_path = json.load(open('getgems.json', 'r', encoding='utf-8'))["db_path"]

def enter_last_time(db_path=db_path, timestamp = now()):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE config SET NOW = ? WHERE rowid = 1", (timestamp,))
    conn.commit()
    
    conn.close()
    
def get_last_time(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT NOW FROM config LIMIT 1")
    last_time = cursor.fetchone()
    
    conn.close()
    
    return last_time[0]
  
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

def fetch_config_data(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM config LIMIT 1")
    config_data = cursor.fetchone()
    
    conn.close()
    
    config_data_list = list(config_data) if config_data else []
    db_path = config_data_list[3]
    return config_data_list

def fetch_senders_data(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM senders")
    senders_data = cursor.fetchall()
    
    conn.close()
    
    senders_data_list = [list(row) for row in senders_data]
    return senders_data_list

def get_senders_data_by_address(address, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM senders WHERE collection_address = ?", (address,))
    senders_data = cursor.fetchall()
    
    conn.close()
    
    senders_data_list = [list(row) for row in senders_data]
    return senders_data_list

def get_senders_data_by_id(id, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM senders WHERE telegram_id = ?", (id,))
    senders_data = cursor.fetchall()
    
    conn.close()
    
    senders_data_list = [list(row) for row in senders_data]
    return senders_data_list

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
    
    return True if senders_data else False

def update_full_senders_data(updated_senders_data, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for sender in updated_senders_data:
        cursor.execute('''
            UPDATE senders
            SET collection_address = ?, telegram_id = ?, last_time = ?
            WHERE id = ?
        ''', (sender[0], sender[1], sender[2], sender[3]))
    
    conn.commit()
    conn.close()

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

def update_senders_data(sender, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE senders
        SET collection_address = ?, telegram_id = ?, last_time = ?
        WHERE id = ?
    ''', (sender[0], sender[1], sender[2], sender[3]))
    conn.commit()
    
    conn.close()
    
def delete_senders_data(address, id, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM senders
        WHERE collection_address = ? AND telegram_id = ?
    ''', (address, id))
    conn.commit()
    
    conn.close()
    
def insert_senders_data(sender, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO senders (collection_address, telegram_id, last_time, telegram_user, language, name)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (sender[0], sender[1], now(), sender[2], sender[3], sender[4]))
    conn.commit()
    
    conn.close()
    
def get_random_proxy(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM proxy ORDER BY RANDOM() LIMIT 1")
    proxy = cursor.fetchone()
    
    conn.close()
    
    return [x for x in proxy] if proxy else None