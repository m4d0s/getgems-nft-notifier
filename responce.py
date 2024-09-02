import aiohttp
import json
import random
import sqlite3
import ipaddress
import asyncio
from database import get_logger

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
logger = get_logger()
db_path = config['db_path']
ipv6_mask = config['ipv6']
api_url = config['api_url']
max_retries = 5
initial_sleep = 5
max_concurrent_requests = 10
semaphore = asyncio.Semaphore(max_concurrent_requests)

async def get_responce(session: aiohttp.ClientSession, json_data: dict, tries: int = 3, sleep: int = 1, proxy: bool = True) -> dict | None:
    error = None
    proxy_url = None

    # Если маска IPv6 задана и это не локальный адрес
    if ipv6_mask and not is_local_address(ipv6_mask):
        ipv6_addr = generate_ipv6(ipv6_mask)
        connector = aiohttp.TCPConnector(ssl=False, local_addr=(ipv6_addr, 0))
        async with aiohttp.ClientSession(connector=connector) as session:
            return await _make_request(session, json_data)
    elif proxy:
        proxy_url = get_proxy()

    # Пытаемся выполнить запрос с retries
    for attempt in range(1, tries + 1):
        if attempt > 1:
            logger.info(f"Retry #{attempt} after {sleep} seconds")
        
        try:
            async with semaphore:  # Ограничение параллелизма
                return await _make_request(session, json_data, proxy_url)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            error = e
            logger.error(f"Request failed: {e}. Retrying in {sleep} seconds...")
            await asyncio.sleep(sleep)
            sleep = min(sleep * 2, 60)  # Увеличиваем время задержки с ограничением до 60 сек
    
    logger.error(f"Failed after {tries} attempts: {error}")
    return None

async def _make_request(session: aiohttp.ClientSession, json_data: dict, proxy_url: str = None) -> dict | None:
    headers = {
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
    }
    
    async with session.post(api_url, json=json_data, headers=headers, proxy=proxy_url) as response:
        response.raise_for_status()
        data = await response.json()
        
        if 'errors' in data:
            logger.error(f"Error in response: {data['errors']}")
            return None
        
        return data

async def coinmarketcap_price(cmc_api, ids) -> dict:
    apiurl = 'https://pro-api.coinmarketcap.com'
    resp = "/v1/cryptocurrency/quotes/latest"
    url = apiurl + resp
    parameters = {
        'id': ','.join([str(i) for i in ids]),
        'convert': 'USD'
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': cmc_api,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=parameters) as response:
            if response.status == 200:
                prices = {}
                data = await response.json()
                for id in ids:
                    try:
                        name = data['data'][str(id)]['symbol']
                        price = data['data'][str(id)]['quote']['USD']['price']
                        logger.info(f"The current price of {name} ({id}) in USD is: ${price:.2f}")
                        prices[id] = [price, name]
                    except KeyError:
                        logger.error(f"Data for id {id} not found in the response.")
                        return None
                return prices
            else:
                logger.error(f"Error: {response.status}, {await response.text()}")
                return None
  
def get_proxy():
  proxy = get_random_proxy()
  if proxy:
    link = proxy[0]  
    logger.info(f"Using proxy: {link.split('@')[-1]}")
    return link
  return None

def generate_ipv6(mask):
    # Преобразуем маску в IPv6-сеть
    network = ipaddress.IPv6Network(mask)
    
    # Получаем сетевой адрес и количество доступных хостов
    network_address = int(network.network_address)
    num_addresses = network.num_addresses
    
    # Генерируем случайное смещение в пределах диапазона сети
    random_offset = random.randint(0, num_addresses - 1)
    
    # Формируем случайный IPv6-адрес
    random_ipv6_address = ipaddress.IPv6Address(network_address + random_offset)
    
    return str(random_ipv6_address)

#proxy
def get_random_proxy(db_path=db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM proxy ORDER BY RANDOM() LIMIT 1")
    proxy = cursor.fetchone()
    
    conn.close()
    
    return [x for x in proxy] if proxy else None

def is_local_address(ipv6_address):
    # Проверяем link-local адреса
    if ipv6_address.startswith('fe80::'):
        return True
    # Проверяем loopback адрес
    if ipv6_address == '::1':
        return True
    # Проверяем unique local адреса (ULA)
    if ipv6_address.startswith('fd') or ipv6_address.startswith('fc'):
        return True
    return False