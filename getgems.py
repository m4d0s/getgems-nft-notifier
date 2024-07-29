import requests
import asyncio
import sqlite3
import json
import time
import re
import datetime
import asyncio
import TonTools
import logging
import pytonapi
from enum import Enum
from tonsdk.contract import Address
from logging import log
from pycoingecko import CoinGeckoAPI
from db_util import get_price

from date_util import now
from db_util import fetch_data, update_senders_data, get_last_time, enter_last_time, enter_price

# loggining config
logging.basicConfig(
    filename=f'bot.log',
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# just some needed values
json_data = json.load(open('getgems.json', 'r', encoding='utf-8'))
api_url, queries = json_data['api_url'], json_data['queries']


#Enum variables for XItem classes
class SocialLinksType(Enum):
  Standart = "Standart"
  Sorted = "Sorted"

class ContentType(Enum):
  Image = "image"
  Video = "video"
  Both = "both"
  NotLoaded = "not_loaded"

class AddressType(Enum):
  Bouncable = "user_friendly"
  Unbouncable = "contract"
  Raw = "raw"

class HistoryType(Enum):
    Mint = "Mint"
    Transfer = "Transfer"
    CancelSale = "CancelSale"
    Sold = "Sold"
    PutUpForSale = "PutUpForSale"
    PutUpForAuction = "PutUpForAuction"
    CancelAuction = "CancelAuction"
    Burn = "Burn"

class NftStatusType(Enum):
  NotForSale = 0,
  ForSale = 1,
  ForAuction = 2

class SaleType(Enum):
  Getgems = 0,
  Other = 1

class AuctionType(Enum):
  Getgems = 0,
  Other = 1


# XItem classes for better-serving of data
class HistoryItem:
    def __init__(self, data):
        try:
            self.type = HistoryType[data['typeData']['historyType']]
        except KeyError:
            return None
        self.name = data['nft']['name']
        self.address = data['nft']['address']
        self.collection = data['collectionAddress']
        self.time = data['time']
        if data['typeData']['historyType'] == 'Sold':
          self.sold = SoldItem(data['typeData'])
        else:
          self.sold = None
    def __repr__(self):
        return f"HistoryItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class SoldItem:
    def __init__(self, data):
      self.amount = PriceItem({
        'price': int(data['price']),
        'currency': 'TON',
        'market_fee': int(data['price']) * 0.05,
        'royalty_fee': int(data['price']) * 0.05,
        'network_fee': 0,
      })
      self.new = data['newOwnerUser']
      self.old = data['oldOwnerUser']
    def __repr__(self):
        return f"SoldType({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class SocialLinksItem:
    def __init__(self, data, type:SocialLinksType = SocialLinksType.Standart):
      self.links = []
      if type == SocialLinksType.Standart:
        for link in data:
          if "twitter" in link.lower() or "x.com" in link:
            self.links.append([link, 'Twitter'])
          elif "t.me" in link.lower() or "telegram.me" in link.lower():
            self.links.append([link, f'Telegram : @{link.split("/")[3].split("/")[0]}'])
          elif "youtube" in link.lower():
            self.links.append([link, 'Youtube'])
          elif "discord" in link.lower():
            self.links.append([link, 'Discord'])
          elif "vk" in link.lower():
            self.links.append([link, 'VK'])
          elif "instagram" in link.lower():
            self.links.append([link, 'Instagram'])
          elif "tiktok" in link.lower():
            self.links.append([link, 'TikTok'])
          else:
            name = self.extract_main_domain(link)
            self.links.append([link, name])
      elif type == SocialLinksType.Sorted:
        for link in data:
          if link['type'] == 'Twitter':
            self.links.append([link['url'], 'Twitter'])
          elif 'Telegram' in link['type']:
            self.links.append([link['url'], f'Telegram : @{link["url"].split("/")[3].split("/")[0]}'])
          elif link['type'] == 'Youtube':
            self.links.append([link['url'], 'Youtube'])
          elif link['type'] == 'Discord':
            self.links.append([link['url'], 'Discord'])
          elif link['type'] == 'VK':
            self.links.append([link['url'], 'VK'])
          elif link['type'] == 'Instagram':
            self.links.append([link['url'], 'Instagram'])
          elif link['type'] == 'TikTok':
            self.links.append([link['url'], 'TikTok'])
          else:
            self.links.append([link['url'], self.extract_main_domain(link['url'])])
      else:
        log(logging.ERROR, "Classification error in SocialLinksItem")
    def __repr__(self):
        return f"SocialLinks({self.links})"
    def extract_main_domain(self, url: str):
      # Регулярное выражение для извлечения домена
      domain_regex = re.compile(r'^(?:http[s]?://)?(?:www\.)?([^:/\s]+)')
      match = domain_regex.search(url)
      if match:
          return match.group(1)
      return None

class UserItem:
    def __init__(self, data):
        self.wallet = data['wallet']
        if data['telegram']['hasTelegram'] is False or data['telegram'] is None:
          self.telegram = ""
        else:
          self.telegram = data['telegram']['userName']
        self.name = data['name']
        self.lang = data['lang']
        self.socialLinks = SocialLinksItem(data['socialLinks'], SocialLinksType.Sorted)
    def __repr__(self):
        return f"UserItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class CollectionItem:
    def __init__(self, data):
        self.address = data['address']
        self.name = data['name']
        self.description = data['description']
        self.owner = UserItem(data['owner'])
        self.socialLinks = SocialLinksItem(data['socialLinks'])
    def __repr__(self):
        return f"CollectionItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"  

class AttributeItem:
    def __init__(self, data, rarity = False):
        # self.displayType = data['displayType']
        self.name = data['traitType']
        self.value = data['value']
        if rarity:
          try:
            self.rarity.max_count = data['maxShapeCount']
            self.rarity.percent = data['rarityPercent']
          except:
            self.rarity = None
        else:
          self.rarity = None
    def __repr__(self):
        return f"AttributeItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class VideoItem:
    def __init__(self, data):
        self.url = data['baseUrl']
        self.preview = data['preview']
        self.sized = data['sized']
    def __repr__(self):
        return f"VideoItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class ImageItem:
    def __init__(self, data):
        self.url = data['baseUrl']
        self.preview = data['preview']
        self.sized = data['sized']
    def __repr__(self):
        return f"ImageItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class ContentItem:
    def __init__(self, data):
      self.original = data['originalUrl']
      self.image = None
      self.video = None
      self.type = ContentType.NotLoaded
      try:
        xd = data['notLoaded']
        if xd:
          self.type = ContentType.NotLoaded
          self.image = None
          self.video = None
      except:
        pass
      try:
        self.image = ImageItem(data['image'])
        self.type = ContentType.Image
      except KeyError:
        self.image = None
        logging.warning(f"Image not found for {data['originalUrl']}")
      try:
        self.video = VideoItem(data)
        self.type = ContentType.Video
      except KeyError:
        self.video = None
        logging.warning(f"Video not found for {data['originalUrl']}")
      if self.image is None and self.video is None:
        self.type = ContentType.NotLoaded
      elif self.image is not None and self.video is not None:
        self.type = ContentType.Both
    def __repr__(self):
        return f"ContentType({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"  

class BidItem:
    async def __init__(self, data):
      self.user = await get_user_info(data['lastBidAddress'])
      self.time = data['lastBidAt']

class PriceItem:
    def __init__(self, data):
      self.amount = float(data['price']) / 10**9
      self.currency = data['currency']
      self.market_fee = float(data['market_fee']) / 10**9
      self.royalty_fee = float(data['royalty_fee']) / 10**9
      self.network_fee = float(data['network_fee']) / 10**9
      self.real_cost()
      
    def __repr__(self):
        return f"PriceItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
    def real_cost(self):
      ton_price = get_price()
      self.usd_amount = self.amount * ton_price
      self.usd_market_fee = self.market_fee * ton_price
      self.usd_royalty_fee = self.royalty_fee * ton_price
      self.usd_network_fee = self.network_fee * ton_price
    def usd_cost(self, amount):
      return amount * get_price()

class AuctionItem:
    def __init__(self, data):
      if data['lastBidUser'] is None:
        self.last_bid = None
      else:
        self.last_bid = BidItem({'lastBidAddress': data['lastBidUser']['wallet'], 'lastBidAt': data['lastBidAt']})
      self.type = data['type']
      if data['type'] == AuctionType.Getgems:
        price = int(data['price']) if data['price'] is not None else int(data['minBid'])
        self.price = PriceItem({
        'price': int(data['price']) ,
        'currency': 'TON',
        'market_fee': price * float(data['marketplaceFeePercent']),
        'royalty_fee': price * float(data['royaltyPercent']),
        'network_fee': int(data['networkFee']),
        })
        
        # price['price'] = data['minBid']
        self.min_bid = PriceItem({
        'price': int(data['minBid']),
        'currency': 'TON',
        'market_fee': int(data['minBid']) * float(data['marketplaceFeePercent']),
        'royalty_fee': int(data['minBid']) * float(data['royaltyPercent']),
        'network_fee': int(data['networkFee']),
        })
        
        # price['price'] = data['maxBid']
        max_bid = int(data['maxBid']) if data['maxBid'] is not None else -1
        self.max_bid = PriceItem({
        'price': max_bid,
        'currency': 'TON',
        'market_fee': max_bid * float(data['marketplaceFeePercent']) if max_bid > 0 else 0,
        'royalty_fee': max_bid * float(data['royaltyPercent']) if max_bid > 0 else 0,
        'network_fee': int(data['networkFee']) if max_bid > 0 else 0,
        })
        
        # self.min_step = data['minStep']
        self.next_bid = PriceItem({
        'price': int(data['minNextBid']),
        'currency': 'TON',
        'market_fee': int(data['minNextBid']) * float(data['marketplaceFeePercent']),
        'royalty_fee': int(data['minNextBid']) * float(data['royaltyPercent']),
        'network_fee': int(data['minNextBid']),
        })
        
        self.nft_owner = data['nftOwnerAddressUser']
        self.finish_at = data['finishAt']
        self.link = f'https://getgems.io/nft/{data["address"]}'
        
      else:
        price = int(data['lastBidAmount']) if data['lastBidAmount'] is not None else int(data['nextBidAmount'])
        self.price = PriceItem({
        'price': price,
        'currency': 'TON',
        'market_fee': price * float(data['marketplaceFeePercent']),
        'royalty_fee': price * float(data['royaltyPercent']),
        'network_fee': 0,
        })
        
        # price['price'] = data['nextBidAmount']
        self.next_bid = PriceItem({
        'price': int(data['nextBidAmount']),
        'currency': 'TON',
        'market_fee': int(data['nextBidAmount']) * float(data['marketplaceFeePercent']),
        'royalty_fee': int(data['nextBidAmount']) * float(data['royaltyPercent']),
        'network_fee': 0,
        })
        
        # price['price'] = data['maxBidAmount']
        self.max_bid = PriceItem({
        'price': int(data['maxBidAmount']),
        'currency': 'TON',
        'market_fee': int(data['maxBidAmount']) * float(data['marketplaceFeePercent']),
        'royalty_fee': int(data['maxBidAmount']) * float(data['royaltyPercent']),
        'network_fee': 0,
        })
        
        # price['price'] = data['lastBidAmount']
        self.min_bid = PriceItem({
        'price': int(data['lastBidAmount']),
        'currency': 'TON',
        'market_fee': int(data['lastBidAmount']) * float(data['marketplaceFeePercent']),
        'royalty_fee': int(data['lastBidAmount']) * float(data['royaltyPercent']),
        'network_fee': 0,
        })
        
        self.nft_owner = data['nftOwnerAddressUser']
        self.min_step = (int(data['nextBidAmount']) - int(data['lastBidAmount']))/10**9
        self.finish_at = data['finishAt']
        self.link = data['link']
        
    def __repr__(self):
      return f"BidItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"   

class SaleItem:
    def __init__(self, data):
      self.nft_owner = data['nftOwnerAddressUser']
      self.price = PriceItem({
        'price': int(data['fullPrice']),
        'currency': 'TON',
        'market_fee': int(data['marketplaceFee']),
        'royalty_fee': int(data['royaltyAmount']),
        'network_fee': int(data['networkFee']),
        })
    def __repr__(self):
      return f"SaleItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class NftItem:
    def __init__(self, data):
        self.address = data['address']
        self.name = data['name']
        self.id = data['id']
        self.burned = data['isBurned']
        self.hidden = data['isHiddenByUser']
        self.domain = data['domain']
        self.index = data['index']
        self.version = data['version']
        self.colorscheme = data['colorScheme']
        self.editor = data['editorAddress']
        self.description = data['description']
        self.owner = UserItem(data['owner'])
        self.collection = CollectionItem(data['collection'])
        self.rarity = data['rarityRank']
        self.likes = data['reactionCounters']['likes']
        self.history = data['history']
        self.attributes = [AttributeItem(i, True) for i in data['attributes']]
        self.content = ContentItem(data['content'])
        self.meta_type = data['metadataSourceType']
        self.content_type = data['contentSourceType']
        self.status = data['sale'][1]
        self.sale = data['sale'][2]
    def get_content_url(self, original = True):
      if self.content.type == ContentType.IMAGE:
        return self.content.image.baseUrl if original else self.content.image.preview | self.content.image.sized
      elif self.content.type == ContentType.VIDEO or self.content.type == ContentType.Both:
        return self.content.video.baseUrl if original else self.content.video.preview | self.content.video.sized
      else: 
        return None
    
    def __repr__(self):
        return f"NftItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"


# get-funcs to scratch data from Getgems GraphQL API
async def get_user_info(user_address: str) -> UserItem:
    query = queries['get_user_info']
    variables = {
        "address": user_address
    }

    data = await get_responce(json_data={'query': query, 'variables': variables})
    if data['data']['userByAddress'] is None or len(data['data']['userByAddress']) == 0:
        variables = {
        "address": address_converter(user_address, AddressType.Unbouncable)
        }
        data = await get_responce(json_data={'query': query, 'variables': variables})
    return UserItem(data['data']['userByAddress'])
  
async def nft_collection_history(collection_address: str, TON_API, first = 10) -> list[HistoryItem]:
    query = queries['nft_collection_history']
    variables = {
        "collectionAddress": collection_address,
        "first": first,
    }

    all_items = []
    data = await get_responce(json_data={'query': query, 'variables': variables})
    if data is None:
        return None

    nft_items = data['data']['historyCollectionNftItems']['items']
    for item in nft_items:
        if item['typeData']['historyType'] == 'Sold' or item['typeData']['historyType'] == 'Transfer':
          item['typeData']['newOwnerUser'] = await get_user_info(item['typeData']['newOwner'])
          item['typeData']['oldOwnerUser'] = await get_user_info(item['typeData']['oldOwner'])
        history = HistoryItem(item)
        all_items.append(history)
    logging.info(f"Items in history: {all_items}")
    return all_items

async def get_nft_owner(nft_address: str) -> UserItem:
    query = queries['get_nft_owner']
    variables = {
        "address": nft_address,
        "first": 1
    }

    data = await get_responce(json_data={'query': query, 'variables': variables})
    if data is None:
        return None
    return UserItem(data['data']['reactionsNft']['nft']['owner'])

async def get_sale_info(history: HistoryItem, first = 1) -> SaleType | AuctionType | None:
  query_native = queries['get_sale_info']['native']
  query_extend = queries['get_sale_info']['extend']
  variables = {
    "address": history.address,
    "first": first
  }
  
  typeofsale = None
  nfttstatus = NftStatusType.NotForSale
  owner = await get_nft_owner(history.address)
  
  responce_native_data = await get_responce(json_data={'query': query_native, 'variables': variables})
  native_data = responce_native_data['data']['reactionsNft']['nft']['sale']           
                                          
  if native_data is not None and len(native_data) != 0:
      if native_data['__typename'] == 'NftSaleFixPrice':
        typeofsale = SaleType.Getgems
        nftstatus = NftStatusType.ForSale
        native_data['nftOwnerAddressUser'] = owner
        native_data['type'] = typeofsale
        native_data['status'] = nftstatus
        sale = SaleItem(native_data)
        
        return [typeofsale, nftstatus, sale]
      
      elif native_data['__typename'] == 'NftSaleAuction':
        typeofsale = AuctionType.Getgems
        nftstatus = NftStatusType.ForAuction
        native_data['type'] = typeofsale
        native_data['status'] = nftstatus
        native_data['nftOwnerAddressUser'] = owner
        auction = AuctionItem(native_data)
        
        return [typeofsale, nftstatus, auction]
      
  else:
    responce_extended_data = await get_responce(json_data={'query': query_extend, 'variables': variables})
    extended_data = responce_extended_data['data']['reactionsNft']['nft']['sale']
    if extended_data is not None and len(extended_data) != 0:
      if extended_data['__typename'] == 'NftSaleFixPriceDisintar':
        typeofsale = SaleType.Other
        nftstatus = NftStatusType.ForSale
        extended_data['type'] = typeofsale
        extended_data['status'] = nftstatus
        extended_data['nftOwnerAddressUser'] = owner
        sale = SaleItem(extended_data)
        
        return [typeofsale, nftstatus, sale]
      
      elif extended_data['__typename'] == 'TelemintAuction':
        typeofsale = AuctionType.Other
        nftstatus = NftStatusType.ForAuction
        extended_data['type'] = typeofsale
        extended_data['status'] = nftstatus
        extended_data['nftOwnerAddressUser'] = owner
        auction = AuctionItem(extended_data)
        
        return [typeofsale, nftstatus, auction]
    else:
      return [None, NftStatusType.NotForSale, None]

async def get_nft_info(history: HistoryItem, first = 1, width = 300, height = 300) -> NftItem:
  query = queries['get_nft_info']
  json_data = {
    "query": query,
    "variables": {
      "address": history.address,
      "first": first,
      "width": width,
      "height": height
    }
  }
  
  responce = await get_responce(json_data)
  data = responce['data']['reactionsNft']['nft']
  data['history'] = history
  data['sale'] = await get_sale_info(history)
  nft = NftItem(data)
  logging.info(f"NFT info: {nft}")
  return nft

async def get_collection_info(collection_address: str) -> dict:
    query = queries['get_collection_info']
    variables = {
        "address": collection_address
    }

    data = await get_responce(json_data={"query": query, "variables": variables})
    data = data['data']['nftCollectionByAddress']
    logging.info("Collection info: " + str(data))
    return data


# other funcs
async def get_separate_history_items(collection_address:str, TON_API:str, first) \
                                                  -> dict[str, list[HistoryItem]]:
  all = await nft_collection_history(collection_address, TON_API=TON_API, first=first)
  new = []
  for item in all:
    if item.time > get_last_time():
      new.append(item)
  sep = separate_history_items(new)
  return sep

async def get_responce(json_data, tries = 3, sleep = 1) -> dict | None:
  error = None
  for i in range(tries+1):
    if i > 0:
      log(logging.INFO, f"Retry to get_response number {i}")
    try:
        response = requests.post(api_url, json=json_data)
        response.raise_for_status()
        data = response.json()
        if 'errors' in data:
            logging.error("Произошла ошибка:")
            logging.error(data['errors'])
            return None
        return data
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
      time.sleep(sleep)
      error = e
      continue
  logging.error(f"Ошибка при выполнении запроса: {error}")

async def tonapi_get_data(key, address, tries = 3, sleep = 1) -> dict | None:
  for i in range(tries+1):
    if i > 0:
      log(logging.INFO, f"Retry to get_response number {i}")
    try:
        client = pytonapi.AsyncTonapi(key)
        nft = await client.nft.get_item_by_address(address)
        if nft is None:
            raise Exception(f"tonapi_get_data: can't find item with address {address}")
        return nft
    except Exception as e:
        logging.error(f"tonapi_get_data: {e}")
        time.sleep(sleep)

def separate_history_items(all_items: list[HistoryItem]) -> dict[str, list[HistoryItem]]:
    if all_items is None or len(all_items) == 0:
        return {
            "Sold": [],
            "PutUpForSale": [],
            "PutUpForAuction": [],
            "Other": []
        }

    sold, on_auc, on_sale, other = [],[],[],[]
    for item in all_items:
        if item is None:
            raise ValueError("item cannot be None")

        if item.type == HistoryType.Sold:
            sold.append(item)
        elif item.type == HistoryType.PutUpForSale:
            on_sale.append(item)
        elif item.type == HistoryType.PutUpForAuction:
            on_auc.append(item)
        else:
            other.append(item)

    return {
        "Sold": sold,
        "PutUpForSale": on_auc,
        "PutUpForAuction": on_sale,
        "Other": other
    }

def address_converter(address, format:AddressType = AddressType.Bouncable) -> str:
    try:
        # Создаем объект Address из входного адреса
        addr = Address(address)
        
        if format == AddressType.Bouncable:
            return addr.to_string(True, True, True)
        elif format == AddressType.Unbouncable:
            return addr.to_string(True, True, False)
        elif format == AddressType.Raw:
            return addr.to_string(False, True, True)
    except Exception as e:
        return f"Error converting address: {e}"  

def coinmarketcup_price(id=11419) -> float:
  apiurl = 'https://pro-api.coinmarketcap.com'
  resp = "/v1/cryptocurrency/quotes/latest"
  url = apiurl + resp
  parameters = {
      'id': id,
      'convert': 'USD'
  }
  headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': 'e4b75a3b-01ab-465b-982d-d64a1a687ffd',
  }
  
  response = requests.get(url, headers=headers, params=parameters)
  
  if response.status_code == 200:
      data = response.json()
      try:
          ton_price = data['data'][str(id)]['quote']['USD']['price']
          logging.info(f"The current price of TON in USD is: ${ton_price:.2f}")
          return ton_price
      except KeyError:
          logging.error(f"Data for 'TON' not found in the response.")
          return None
  else:
      logging.error(f"Error: {response.status_code}, {response.text}")
      return None