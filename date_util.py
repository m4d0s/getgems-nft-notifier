from datetime import datetime

def now():
    timestamp = int(datetime.now().timestamp())
    return timestamp
def log_format_time():
    dt = datetime.fromtimestamp(now())
    date_str = dt.strftime('%Y%m%d-%H%M')
    return date_str

def date_to_number(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    timestamp = int(dt.timestamp())
    return timestamp

def number_to_date(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
    return date_str
