from datetime import datetime
import logging

logging.basicConfig(
    filename=f'bot.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def date_to_number(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    timestamp = int(dt.timestamp())
    return timestamp

def number_to_date(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    return date_str

def log_format_time(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    date_str = dt.strftime('%Y%m%d%H%M')
    return date_str

def now():
    timestamp = int(datetime.now().timestamp())
    return timestamp
