import requests
import json
import time
import re
import logging
import pytonapi
from enum import Enum
from tonsdk.contract import Address
from logging import log
from db_util import get_price, update_senders_data
from date_util import number_to_date, log_format_time

# loggining config
logging.basicConfig(
  filename=f'logs/{log_format_time()}.log',
  level=logging.INFO, 
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# just some needed values
json_data = json.load(open('getgems.json', 'r', encoding='utf-8'))
api_url, queries = json_data['api_url'], json_data['queries']


#Enum variables for XItem classes
class UserLinkType(Enum):
  Getgems = 0,
  Tonviewer = 1,
  Tonscan = 2,
  Telegram = 3

class SocialLinksType(Enum):
  Standart = "Standart"
  Sorted = "Sorted"

class ContentType(Enum):
  Image = "image"
  Video = "video"
  Both = "both"
  NotLoaded = "not_loaded"

class ContentPlaceType(Enum):
  Local = 0,
  Remote = 1
  def type_by_link(self, link):
    if 'https://' in link or 'http://' in link:
      return ContentPlaceType.Remote
    return ContentPlaceType.Local

class AddressType(Enum):
  Bouncable = "user_friendly"
  Unbouncable = "contract"
  Raw = "raw"

class HistoryType(Enum):
  PutUpForSale = 0
  PutUpForAuction = 1
  Sold = 2
  CancelSale = 3
  CancelAuction = 4
  Mint = 5
  Transfer = 6
  Burn = 7

class NftStatusType(Enum):
  NotForSale = 0,
  ForSale = 1,
  ForAuction = 2

class MarketplaceType(Enum):
  Getgems = 0,
  Other = 1


# XItem classes for better-serving of data
class HistoryItem:
  def __init__(self, data):
    self.time = data['time']
    try:
      self.type = HistoryType[data['typeData']['historyType']]
    except KeyError:
      return None
    self.name = data['nft']['name']
    self.address = data['nft']['address']
    self.collection = data['collectionAddress']
    if data['typeData']['historyType'] == 'Sold':
      data['typeData']['address'] = self.address
      self.sold = SoldItem(data['typeData'])
    else:
      self.sold = None
  def __repr__(self):
    return f"HistoryItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class SocialLinksItem:
  def __init__(self, data, type:SocialLinksType = SocialLinksType.Standart):
    self.links = []
    if data is None or len(data) == 0: 
      return
    elif type == SocialLinksType.Standart:
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
  def get_link(self, type:UserLinkType):
    if type == UserLinkType.Getgems:
      return f"https://getgems.io/user/{self.wallet}"
    elif type == UserLinkType.Tonviewer:
      return f"https://tonviewer.com/{self.wallet}"
    elif type == UserLinkType.Telegram and self.telegram != "":
      return f'https://t.me/{self.telegram}'
    elif type == UserLinkType.Telegram and self.telegram == "":
      return ""
    
  def __repr__(self):
    return f"UserItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class CollectionItem:
  def __init__(self, data):
    self.address = data['address']
    self.name = data['name']
    self.description = data['description']
    self.owner = UserItem(data['owner'])
    self.socialLinks = SocialLinksItem(data['socialLinks'])
    self.holders_count = data['approximateHoldersCount']
    self.items_count = data['approximateItemsCount']
    self.isRarity = data['hasRarityAttributes']
  def __repr__(self):
    return f"CollectionItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"  
  def get_url(self, type = UserLinkType.Getgems):
    if type == UserLinkType.Getgems:
      return f"https://getgems.io/collection/{self.address}"
    elif type == UserLinkType.Tonviewer:
      return f"https://tonviewer.com/{self.address}"

class AttributeItem:
  def __init__(self, data, rarity = False):
    # self.displayType = data['displayType']
    self.name = data['traitType']
    self.value = data['value']
    if rarity and 'rarityPercent' in data:
      self.rarity.max_count = data['maxShapeCount']
      self.rarity.percent = data['rarityPercent']
    else:
      self.rarity = None
  def __repr__(self):
    return f"AttributeItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  def text(self):
    t = f"  <b>{self.name}</b>: {self.value}"
    if self.rarity is not None:
      t += f" ({self.rarity.percent}%)"
    return t

class VideoItem:
  def __init__(self, data):
    self.url = data['baseUrl']
    self.preview = data['preview']
    self.sized = data['sized']
  def __repr__(self):
    return f"VideoItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  def get_url(self):
    return self.sized if self.sized is not None \
    else self.url if self.url is not None \
    else self.preview if self.preview is not None \
    else None
    
class ImageItem:
  def __init__(self, data):
    self.url = data['baseUrl']
    self.preview = data['preview']
    self.sized = data['sized']
  def __repr__(self):
    return f"ImageItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  
  def get_url(self):
    return self.sized if self.sized is not None \
    else self.url if self.url is not None \
    else self.preview if self.preview is not None \
    else None

class ContentItem:
  def __init__(self, data):
    self.image = None
    self.video = None
    self.original = data['notLoadedContent']
    self.type = ContentType.NotLoaded
    
    if 'notLoaded' in data:
      self.locate = ContentPlaceType.type_by_link(self.original)
    else:
      self.original = data['originalUrl']
    
    if 'image' in data:
      data['image']['notLoadedContent'] = data['notLoadedContent']
      self.image = ImageItem(data['image'])
      self.type = ContentType.Image
    
    if 'baseUrl' in data:
      self.video = VideoItem(data)
      self.type = ContentType.Video
    
    if self.image is not None and self.video is not None:
      self.type = ContentType.Both
  def __repr__(self):
    return f"ContentType({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  
  def get_url(self, original = True):
    if self.type == ContentType.Image:
      return self.image.get_url()  
    if self.type == ContentType.Video or self.type == ContentType.Both:
      return self.video.get_url()
    else:
      return self.original
        

class BidItem:
  def __init__(self, data):
    self.user = data['lastBidAddress']
    self.time = data['lastBidAt']
  
  def __repr__(self) -> str:
    return f"BidItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class PriceItem:
  def __init__(self, data):
    self.price = float(data['price']) / 10**9
    self.currency = data['currency']
    self.market_fee = float(data['market_fee']) / 10**9
    self.royalty_fee = float(data['royalty_fee']) / 10**9
    self.network_fee = float(data['network_fee']) / 10**9
    self.profit = self.price - self.market_fee - self.royalty_fee - self.network_fee
    
    self.usd_amount = 0
    self.usd_market_fee = 0
    self.usd_royalty_fee = 0
    self.usd_network_fee = 0
    self.usd_profit = 0
    self.real_cost()
    
  def __repr__(self):
    return f"PriceItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  def real_cost(self):
    ton_price = get_price()
    self.usd_amount = self.price * ton_price
    self.usd_market_fee = self.market_fee * ton_price
    self.usd_royalty_fee = self.royalty_fee * ton_price
    self.usd_network_fee = self.network_fee * ton_price
    self.usd_profit = self.profit * ton_price
    
    return self.usd_amount
    
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
    self.link = f'https://getgems.io/nft/{data["address"]}'
    
  def details(self):
    text = [f"<b>Продано за:</b> {format_number(self.amount.price)} {self.amount.currency} ({format_number(self.amount.real_cost())}$)",
            f"<b>Новый владельец:</b> <a href=\"{self.new.get_link(UserLinkType.Tonviewer)}\">{short_address(self.new.wallet)}</a>",
            f"<b>Старый владельец:</b> <a href=\"{self.old.get_link(UserLinkType.Tonviewer)}\">{short_address(self.old.wallet)}</a>"]
    return '\n'.join(text)
  def __repr__(self):
    return f"SoldType({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class AuctionItem:
  def __init__(self, data):
    if 'lastBidUser' in data or data['lastBidUser'] is None:
      self.last_bid = None
    else:
      self.last_bid = data['bid']
    self.type = data['type']
    self.link = data['link'] if 'link' in data and data['link'] is not None \
                  else f'https://getgems.io/nft/{data["address"]}'
    if data['type'] == MarketplaceType.Getgems:
      price = int(data['price']) if data['price'] is not None else int(data['minNextBid'])
      self.price = PriceItem({
      'price': int(data['price']),
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
      
      self.min_step = self.next_bid.price - price
      self.nft_owner = data['nftOwnerAddressUser']
      self.finish_at = data['finishAt']
      
    else:
      price = int(data['lastBidAmount']) if data['lastBidAmount'] is not None and int(data['lastBidAmount']) > 0 \
              else int(data['nextBidAmount']) if 'nextBidAmount' in data and int(data['nextBidAmount']) > 0 \
              else int(data['minNextBid']) if 'minNextBid' in data and int(data['minNextBid']) > 0 \
              else int(data['minBid'])
      self.price = PriceItem({
      'price': price,
      'currency': 'TON',
      'market_fee': price * float(data['marketplaceFeePercent']),
      'royalty_fee': price * float(data['royaltyPercent']),
      'network_fee': 0,
      })
      
      # price['price'] = data['nextBidAmount']
      next_bid = int(data['nextBidAmount']) if 'nextBidAmount' in data and data['nextBidAmount'] is not None else price
      self.next_bid = PriceItem({
      'price': next_bid,
      'currency': 'TON',
      'market_fee': next_bid * float(data['marketplaceFeePercent']),
      'royalty_fee': next_bid * float(data['royaltyPercent']),
      'network_fee': 0,
      })
      
      # price['price'] = data['maxBidAmount']
      max_bid = int(data['maxBidAmount']) if 'maxBidAmount' in data and data['maxBidAmount'] is not None and int(data['maxBidAmount']) > 0 \
        else int(data['maxBid']) if 'maxBid' in data and  data['maxBid'] is not None and int(data['maxBid']) > 0 \
        else -1
        
      self.max_bid = PriceItem({
      'price': max_bid,
      'currency': 'TON',
      'market_fee': max_bid * float(data['marketplaceFeePercent']) if max_bid > 0 else 0,
      'royalty_fee': max_bid * float(data['royaltyPercent']) if max_bid > 0 else 0,
      'network_fee': 0,
      })
      
      # price['price'] = data['lastBidAmount']
      self.min_bid = PriceItem({
      'price': price,
      'currency': 'TON',
      'market_fee': price * float(data['marketplaceFeePercent']),
      'royalty_fee': price * float(data['royaltyPercent']),
      'network_fee': 0,
      })
      
      self.nft_owner = data['nftOwnerAddressUser']
      self.min_step = int(data['minStep']) / 100 * price if 'minStep' in data and 1 <=int(data['minStep']) <= 100 \
                      else float(data['minStep']) * price if 'minStep' in data and  1 > int(data['minStep'])\
                      else price - next_bid
      self.finish_at = data['finishAt']
    
  def details(self):
    text = [f"<b>Выставил на продажу:</b> <a href=\"{self.nft_owner.get_link(UserLinkType.Tonviewer)}\">{short_address(self.nft_owner.wallet)}</a>",
      f"<b>Текущая цена:</b> {format_number(self.price.price)} {self.price.currency} ({format_number(self.price.real_cost())}$)",
      #  f"*Минимальная цена:* {self.min_bid.price} {self.min_bid.currency} ({self.min_bid.real_cost()} $)",
      f"<b>Максимальная цена:</b> {format_number(self.max_bid.price)} {self.max_bid.currency} ({format_number(self.max_bid.real_cost())}$)" if self.max_bid.price > 0 \
                          else "<b>Максимальная цена: отсутствует</b>",
      f"<b>Следующая цена:</b> {format_number(self.next_bid.price)} {self.next_bid.currency} ({format_number(self.next_bid.real_cost())}$)",
      f"<b>Минимальный шаг:</b> {format_number(self.min_step)} {self.price.currency}" if self.min_step > 0 else "<b>Минимальный шаг:</b> отсутствует",
      f"<b>Время окончания:</b> {number_to_date(self.finish_at)}"]
    return '\n'.join(text) 
  def __repr__(self):
    return f"BidItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"   

class SaleItem:
  def __init__(self, data):
    self.nft_owner = data['nftOwnerAddressUser']
    self.link = f'https://getgems.io/nft/{data["address"]}'
    self.price = PriceItem({
      'price': int(data['fullPrice']),
      'currency': 'TON',
      'market_fee': int(data['marketplaceFee']),
      'royalty_fee': int(data['royaltyAmount']),
      'network_fee': int(data['networkFee']),
      })
    
  def details(self):
    text = [f"<b>Выставил на продажу:</b> <a href=\"{self.nft_owner.get_link(UserLinkType.Tonviewer)}\">{short_address(self.nft_owner.wallet)}</a>",
            f"<b>Текущая цена:</b> {format_number(self.price.price)} {self.price.currency} ({format_number(self.price.real_cost())}$)"]
    return '\n'.join(text)
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
    if self.collection.isRarity:
      self.attributes = [AttributeItem(i, False) for i in data['attributes']]
    else:
      self.attributes = [AttributeItem(i, True) for i in data['rarityAttributes']]
    self.content = ContentItem(data['content'])
    self.meta_type = data['metadataSourceType']
    self.content_type = data['contentSourceType']
    self.marketplace = data['sale'][0]
    self.status = data['sale'][1]
    self.sale = data['sale'][2]
  def get_content_url(self, original = True):
    if self.content is not None and original and self.content.original is not None: 
      return self.content.original
    else:
      return self.content.get_url()
    
  def notify_text(self):
    header = f'<b>NFT"{self.name}" появилась в продаже!</b>' if self.history.type == HistoryType.PutUpForSale \
            else f'<b>NFT "{self.name}" была продана!</b>' if self.history.type == HistoryType.Sold \
            else f'<b>NFT "{self.name}" была выставлена на аукцион!</b>' if self.history.type == HistoryType.PutUpForAuction \
            else f'<b>NFT "{self.name}" была заминчена!</b>' if self.history.type == HistoryType.Mint \
            else f'<b>NFT "{self.name}" была сожжена!</b>' if self.history.type == HistoryType.Burn \
            else f'<b>NFT "{self.name}" была снята с продажи!</b>' if self.history.type == HistoryType.CancelSale \
            else f'<b>NFT "{self.name}" была снята с аукциона!</b>' if self.history.type == HistoryType.CancelAuction \
            else f'<b>NFT "{self.name}" была отправлена новому владельцу!</b>' if self.history.type == HistoryType.Transfer \
            else f'<i><b>Статус NFT "{self.name}" не определён</b></i>'
    body = self.sale.details() if self.sale is not None else "<i>Детальной информации по транзакции не удалось обнаружить<i>"
    
    unique = f"<b>Уникальность:</b> {self.rarity}/{self.collection.items_count}" if self.collection.isRarity and self.rarity is not None else ""
    likes = f"<b>Реакции:</b> {self.likes}\n" if self.likes is not None else ""
    
    attribs = ["<b>Атрибуты:</b> "]
    if len(self.attributes) != 0:
      for i in self.attributes:
        attribs.append(i.text())
      attribs = unique + likes + '\n'.join(attribs)
    else :
      attribs = unique + likes
    
    footer = (f"<a href=\"{self.owner.get_link(UserLinkType.Tonviewer)}\">Кошелёк владельца</a>"
              f" | <a href=\"{self.owner.get_link(UserLinkType.Getgems)}\">Аккаунт Getgems</a>")
    
    if self.owner.telegram != "":
      footer += f" | <a href=\"{self.owner.get_link(UserLinkType.Telegram)}\">Телеграм</a>"

    return f'{header}\n\n{body}\n\n{attribs}\n\n{footer}'
  def __repr__(self):
      return f"NftItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"


# get-funcs to scratch data from Getgems GraphQL API
async def get_user_info(user_address: str) -> UserItem:
  query = queries['get_user_info']
  variables = {
      "address": user_address
  }

  data = await get_responce(json_data={'query': query, 'variables': variables})
  if data is None or data['data']['userByAddress'] is None or len(data['data']['userByAddress']) == 0:
    variables = {
    "address": address_converter(user_address, AddressType.Unbouncable)
    }
    data = await get_responce(json_data={'query': query, 'variables': variables})
    if data is None or data['data']['userByAddress'] is None or len(data['data']['userByAddress']) == 0:
      data = {"data" :
              { "userByAddress":
                { "wallet" : user_address,
                  "telegram" : {"hasTelegram" : False},
                  "name" : user_address,
                  "lang": "en",
                  "socialLinks": []}}}
  return UserItem(data['data']['userByAddress'])
  
async def get_new_history(senders_data: tuple, TON_API, first = 10, DB_PATH = "sqlite.db") -> list[HistoryItem]:
  query = queries['nft_collection_history']
  variables = {
      "collectionAddress": senders_data[0],
      "first": first,
  }

  all_items = []
  last_time = senders_data[2]
  log_text = f"Items in history (last timestamp: {senders_data[2]}):\n"
  data = await get_responce(json_data={'query': query, 'variables': variables})
  if data is None:
    return []
  nft_items = data['data']['historyCollectionNftItems']['items']
  for item in sorted(nft_items, key=lambda x: x['time'], reverse=True):
    if item['typeData']['historyType'] == 'Sold' or item['typeData']['historyType'] == 'Transfer':
      item['typeData']['newOwnerUser'] = await get_user_info(item['typeData']['newOwner'])
      item['typeData']['oldOwnerUser'] = await get_user_info(item['typeData']['oldOwner'])
    if item['time'] > senders_data[2]:
      history = HistoryItem(item)
      all_items.append(history)
      last_time = senders_data[2]
      log_text += str(history) + "\n"
  senders_data[2] = last_time
  update_senders_data(senders_data)
  logging.info(log_text)
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

async def get_sale_info(history: HistoryItem, first = 1):
  query_native = queries['get_sale_info']['native']
  query_extend = queries['get_sale_info']['extend']
  variables = {
    "address": history.address,
    "first": first
  }
  
  typeofsale = None
  nftstatus = NftStatusType.NotForSale
  owner = await get_nft_owner(history.address)
  
  responce_native_data = await get_responce(json_data={'query': query_native, 'variables': variables})
  native_data = responce_native_data['data']['reactionsNft']['nft']['sale']           
                                          
  if native_data is not None and len(native_data) != 0:
    if native_data['__typename'] == 'NftSaleFixPrice':
      typeofsale = MarketplaceType.Getgems
      nftstatus = NftStatusType.ForSale
      native_data['nftOwnerAddressUser'] = owner
      native_data['type'] = typeofsale
      native_data['status'] = nftstatus
      native_data['address'] = history.address
      sale = SaleItem(native_data)
      
      return [typeofsale, nftstatus, sale]
    
    elif native_data['__typename'] == 'NftSaleAuction':
      typeofsale = MarketplaceType.Other
      nftstatus = NftStatusType.ForAuction
      native_data['type'] = typeofsale
      native_data['status'] = nftstatus
      native_data['nftOwnerAddressUser'] = owner
      native_data['address'] = history.address
      
      if 'lastBidUser' in native_data and native_data['lastBidUser'] is not None:
        native_data['lastBidUser'] = await get_user_info(native_data['lastBidUser']['wallet'])
        native_data['bid'] = BidItem({'lastBidAddress': native_data['lastBidUser'], 
                                        'lastBidAt': native_data['lastBidAt']}) \
                                          if 'lastBidUser' in native_data and native_data['lastBidUser'] is not None \
                                          else None
      else:
        native_data['bid'] = None
      auction = AuctionItem(native_data)
      
      return [typeofsale, nftstatus, auction]
      
  else:
    responce_extended_data = await get_responce(json_data={'query': query_extend, 'variables': variables})
    extended_data = responce_extended_data['data']['reactionsNft']['nft']['sale']
    if extended_data is not None and len(extended_data) != 0:
      if extended_data['__typename'] == 'NftSaleFixPriceDisintar':
        typeofsale = MarketplaceType.Getgems
        nftstatus = NftStatusType.ForSale
        extended_data['type'] = typeofsale
        extended_data['status'] = nftstatus
        extended_data['nftOwnerAddressUser'] = owner
        extended_data['address'] = history.address
        sale = SaleItem(extended_data)
        
        return [typeofsale, nftstatus, sale]
      
      elif extended_data['__typename'] == 'TelemintAuction':
        typeofsale = MarketplaceType.Other
        nftstatus = NftStatusType.ForAuction
        extended_data['type'] = typeofsale
        extended_data['status'] = nftstatus
        extended_data['nftOwnerAddressUser'] = owner
        extended_data['address'] = history.address
        if 'lastBidUser' in extended_data and extended_data['lastBidUser'] is not None:
          extended_data['lastBidUser'] = await get_user_info(extended_data['lastBidUser']['wallet'])
          extended_data['bid'] = BidItem({'lastBidAddress': extended_data['lastBidUser'], 
                                        'lastBidAt': extended_data['lastBidAt']}) \
                                          if 'lastBidUser' in extended_data and extended_data['lastBidUser'] is not None \
                                          else None
        else:
          extended_data['bid'] = None
        auction = AuctionItem(extended_data)
        
        return [typeofsale, nftstatus, auction]
    else:
      if history.sold is not None:
        return [None, NftStatusType.NotForSale, history.sold]
      return [None, NftStatusType.NotForSale, None]

async def get_nft_info(history: HistoryItem, first = 1, width = 300, height = 300, notloadedcontent = "notloaded.png") -> NftItem:
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
  data['content']['notLoadedContent'] = notloadedcontent
  nft = NftItem(data)
  logging.info(f"NFT info: {nft}")
  return nft


# other funcs
async def get_collection_info(collection_address: str) -> dict:
    query = queries['get_collection_info']
    variables = {
        "address": collection_address
    }

    data = await get_responce(json_data={"query": query, "variables": variables})
    data = data['data']['nftCollectionByAddress']
    logging.info("Collection info: " + str(data))
    return CollectionItem(data)

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
        client.close()
        if nft is None:
            raise Exception(f"tonapi_get_data: can't find item with address {address}")
        return nft
    except Exception as e:
        logging.error(f"tonapi_get_data: {e}")
        time.sleep(sleep)

def address_converter(address, format:AddressType = AddressType.Unbouncable) -> str:
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

def short_address(address) -> str:
  return f"{address_converter(address)[:4]}...{address_converter(address)[-4:]}"

def format_number(number: float) -> str:
  form_num = [number,""]
  if number >= 1000**3:
    form_num = [number / 1000**3,"B"]
  elif number >= 1000**2:
    form_num = [number / 1000**2,"M"]
  elif number >= 1000**1:
    form_num = [number / 1000**1,"K"]
  
  if form_num[0] % 100 > 1:
    return f"{form_num[0]:.1f}{form_num[1]}"
  elif form_num[0] % 10 > 1:
    return f"{form_num[0]:.2f}{form_num[1]}"
  else:
    return f"{form_num[0]:.3f}{form_num[1]}"

def coinmarketcup_price(cmc_api, id=11419) -> float:
  apiurl = 'https://pro-api.coinmarketcap.com'
  resp = "/v1/cryptocurrency/quotes/latest"
  url = apiurl + resp
  parameters = {
      'id': id,
      'convert': 'USD'
  }
  headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': cmc_api,
  }
  
  response = requests.get(url, headers=headers, params=parameters)
  
  if response.status_code == 200:
    data = response.json()
    try:
      ton_price = data['data'][str(id)]['quote']['USD']['price']
      logging.info(f"The current price of TON in USD is: ${ton_price:.2f}")
      return ton_price
    except KeyError:
      logging.error("Data for 'TON' not found in the response.")
      return None
  else:
    logging.error(f"Error: {response.status_code}, {response.text}")
    return None