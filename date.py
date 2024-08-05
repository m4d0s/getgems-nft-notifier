from datetime import datetime, timedelta, timezone
import time
import json

local_timezone = time.timezone
translate = json.load(open('getgems.json', 'r', encoding='utf-8'))['translate']

def get_tzinfo(offset_hours: int) -> timezone:
    return timezone(timedelta(hours=offset_hours))

def now(offset_hours: int = 0) -> int:
    tzinfo = get_tzinfo(offset_hours)
    return int(datetime.now(tz=tzinfo).timestamp())

def log_format_time(offset_hours: int = 0) -> str:
    tzinfo = get_tzinfo(offset_hours)
    return datetime.now(tz=tzinfo).strftime('%Y%m%d')

def date_to_number(date_str: str, offset_hours: int = 0) -> int:
    tzinfo = get_tzinfo(offset_hours)
    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    dt = dt.replace(tzinfo=tzinfo)
    return int(dt.timestamp())

def number_to_date(timestamp: int, offset_hours: int = 0) -> str:
    tzinfo = get_tzinfo(offset_hours)
    dt = datetime.fromtimestamp(timestamp, tz=tzinfo)
    return dt.strftime('%Y-%m-%d %H:%M:%S' + " " + tzinfo.tzname(dt))

def format_remaining_time(target_time: int, lang = "en") -> str:
    waste = target_time - now()
    prefix = ""
    
    if waste < 0:
        prefix = translate[lang]['date_util'][0]

    days = waste // (3600 * 24)
    hours, remainder = divmod(waste, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Определение формата вывода
    if days > 30:
        months = days // 30
        return f"{months} {translate[lang]['date_util'][1]} {days} {translate[lang]['date_util'][2]} {prefix}"
    elif days > 1:
        return f"{days} {translate[lang]['date_util'][2]} {hours} {translate[lang]['date_util'][3]} {prefix}"
    elif hours > 0:
        return f"{hours} {translate[lang]['date_util'][3]} {minutes} {translate[lang]['date_util'][4]} {prefix}"
    elif minutes > 0:
        return f"{minutes} {translate[lang]['date_util'][4]} {seconds} {translate[lang]['date_util'][5]} {prefix}"
    else:
        return f"{seconds} {seconds} {translate[lang]['date_util'][5]} {prefix}"
