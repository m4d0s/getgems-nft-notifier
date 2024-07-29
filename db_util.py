import requests
import asyncio
import sqlite3
import json
import time
import sqlite3
import logging
from datetime import datetime
from date_util import now, log_format_time

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

db_path = 'sqlite.db'

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
  
def enter_price(value:float, db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE config SET TON_PRICE = ? WHERE rowid = 1", (value,))
    conn.commit()
    conn.close()
    
def get_price(db_path=db_path) -> float:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT TON_PRICE FROM config LIMIT 1")
    last_time = cursor.fetchone()
    conn.close()
    return last_time[0]

def fetch_config_data(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM config LIMIT 1")
    config_data = cursor.fetchone()
    
    conn.close()
    
    # Преобразуем данные в список
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


def update_senders_data(updated_senders_data, db_path=db_path):
  
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