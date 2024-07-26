import requests
import asyncio
import sqlite3
import json
import time
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def fetch_data(db_path="sqlite.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM config LIMIT 1")
    config_data = cursor.fetchone()
    
    cursor.execute("SELECT * FROM senders")
    senders_data = cursor.fetchall()
    
    conn.close()
    
    # Преобразуем данные в списки
    config_data_list = list(config_data) if config_data else []
    senders_data_list = [list(row) for row in senders_data]
    
    return [config_data_list, senders_data_list]


def update_senders_data(updated_senders_data, db_path="sqlite.db"):
  
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