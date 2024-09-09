import aiohttp
import json
import asyncio
import socket
from database import get_logger
from proxy import get_free_proxy, set_proxy_used

config = json.load(open('getgems.json', 'r', encoding='utf-8'))
db_path, ipv6_mask, api_url = config['db_path'], config['ipv6'], config['api_url']
max_retries, initial_sleep, max_concurrent_requests = 5, 5, 10
semaphore = asyncio.Semaphore(max_concurrent_requests)
logger = get_logger()

async def get_responce(json_data: dict, tries: int = 3, sleep: int = 1, proxy: bool = True) -> dict:
    proxy_url = None
    data_return = None
    _proxy = get_free_proxy(full=True)  # Assuming this is an existing function

    async def _make_request(session: aiohttp.ClientSession, proxy_url: str = None,
                            json_data=json_data, sleep=sleep, tries=tries) -> dict:
        headers = {
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
        }
        error = None
        for attempt in range(1, tries + 1):
            if attempt > 1:
                logger.info(f"Retry #{attempt} after {sleep} seconds")  # Assuming logger exists
            try:
                async with semaphore:  # Ensure semaphore is defined or passed properly
                    async with session.post(api_url, json=json_data, headers=headers, proxy=proxy_url) as response:
                        response.raise_for_status()  # Raises an error for bad responses
                        data = await response.json()

                        if 'errors' in data:
                            logger.error(f"Error in response: {data['errors']}")
                            return None
                        return data
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                error = e
                logger.error(f"Request failed: {e}. Retrying in {sleep} seconds...")
                await asyncio.sleep(sleep)
                sleep = min(sleep * 2, 60)  # Incremental backoff
        logger.error(f"Failed after {tries} attempts: {error}")
        return None

    # Check if the proxy is valid and IPv6 logic
    loc_addr = (_proxy[0], 0, 0, 0) if _proxy and _proxy[2] == 'ipv6' else None
    family = socket.AddressFamily.AF_INET6 if _proxy and _proxy[2] == 'ipv6' else socket.AddressFamily.AF_INET
    connector = aiohttp.TCPConnector(ssl=False, local_addr=loc_addr, family=family)

    async with aiohttp.ClientSession(connector=connector) as session:
        proxy_url = _proxy[0] if proxy and _proxy else None
        data_return = await _make_request(session=session, json_data=json_data, proxy_url=proxy_url)
        set_proxy_used(proxy_url, 0)  # Assuming this function exists
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


