from datetime import datetime, timedelta, timezone
import time

local_timezone = time.timezone

def get_tzinfo(offset_hours: int) -> timezone:
    """Создает объект timezone с указанным смещением в часах."""
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
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_remaining_time(target_time: int) -> str:
    waste = target_time - now()
    
    if waste < 0:
        return ""

    days = waste // (3600 * 24)
    hours, remainder = divmod(waste, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # Определение формата вывода
    if days > 30:
        months = days // 30
        return f"{months} мес."
    elif days > 1:
        return f"{days} дн."
    elif days == 1:
        return f"1 дн. {hours} ч. {minutes} мин."
    elif hours > 0:
        return f"{hours} ч. {minutes} мин."
    elif minutes > 0:
        return f"{minutes} мин. {seconds} сек."
    else:
        return f"{seconds} сек."

# def number_to_relative_date(timestamp, timezone = timezone.utc):
#     delta = timedelta(seconds=timestamp)
    
#     date_str = dt.strftime('%Y-%m-%d')
#     return date_str
