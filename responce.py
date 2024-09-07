import aiohttp
import json
import sqlite3
import asyncio
import socket
from database import get_logger
from proxy import is_local_address, get_free_proxy, set_proxy_used

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
db_path, ipv6_mask, api_url = config['db_path'], config['ipv6'], config['api_url']
max_retries, initial_sleep, max_concurrent_requests = 5, 5, 10
semaphore = asyncio.Semaphore(max_concurrent_requests)
logger = get_logger()

async def get_responce(session: aiohttp.ClientSession, json_data: dict, tries: int = 3, sleep: int = 1, proxy: bool = True) -> dict | None:
    proxy_url = None
    data_return = None
    
    async def _make_request(session: aiohttp.ClientSession, json_data: dict, proxy_url: str = None, sleep: int = 1, tries: int = 3, semaphore = semaphore) -> dict | None:
        headers = {
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        error = None
        for attempt in range(1, tries + 1):
            if attempt > 1:
                logger.info(f"Retry #{attempt} after {sleep} seconds")
            try:
                async with semaphore:  # Ограничение параллелизма
                    async with session.post(api_url, json=json_data, headers=headers, proxy=proxy_url) as response:
                        response.raise_for_status()
                        data = await response.json()
                        
                        if 'errors' in data:
                            logger.error(f"Error in response: {data['errors']}")
                            return None
                        return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error = e
                logger.error(f"Request failed: {e}. Retrying in {sleep} seconds...")
                await asyncio.sleep(sleep)
                sleep = min(sleep * 2, 60)  # Увеличиваем время задержки с ограничением до 60 сек
        logger.error(f"Failed after {tries} attempts: {error}")
        return None

    # Если маска IPv6 задана и это не локальный адрес
    if ipv6_mask and not is_local_address(ipv6_mask):
        ipv6_addr = get_free_proxy(version='ipv6') #await generate_ipv6(ipv6_mask)
        connector = aiohttp.TCPConnector(ssl=False, local_addr=(ipv6_addr, 0, 0, 0), family=socket.AddressFamily.AF_INET6)
        async with aiohttp.ClientSession(connector=connector) as session:
            data_return = await _make_request(session, json_data)
    elif proxy:
        proxy_url = get_free_proxy()
        data_return = await _make_request(session, json_data, proxy_url)

    set_proxy_used(proxy_url, 0)
    # await manage_ipv6_address(ipv6_addr, only_del=True)
    return data_return

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


