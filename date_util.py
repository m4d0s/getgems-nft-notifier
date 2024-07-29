from datetime import datetime
import logging

def now():
    timestamp = int(datetime.now().timestamp())
    return timestamp
def log_format_time():
    dt = datetime.fromtimestamp(now())
    date_str = dt.strftime('%Y%m%d%H%M')
    return date_str

logging.basicConfig(
    filename=f'logs/{log_format_time()}.log',
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
