import requests
import json
import re
import asyncio
import aiohttp
from pytonapi import AsyncTonapi
from enum import Enum
from tonsdk.contract import Address
from database import get_price, update_senders_data, get_random_proxy, get_logger
from date import number_to_date, format_remaining_time, now
from datetime import timezone

logger = get_logger()

# just some needed values
json_data = json.load(open('getgems.json', 'r', encoding='utf-8'))
api_url, queries, translate = json_data['api_url'], json_data['queries'], json_data['translate']
max_retries = 5
initial_sleep = 5
max_concurrent_requests = 10
semaphore = asyncio.Semaphore(max_concurrent_requests)

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
  Burn = 7,
  NotForSale = 8

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
      logger.error("Classification error in SocialLinksItem")
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
  def link_user_text(self) -> str:
    return f"<a href=\"{self.get_link(UserLinkType.Tonviewer)}\">{short_address(self.wallet)}</a> (<a href=\"{self.get_link(UserLinkType.Getgems)}\">Getgems</a>)"
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
      self.max_count = data['maxShapeCount']
      self.percent = data['rarityPercent']
    else:
      self.max_count = -1
      self.percent = -1
  def __repr__(self):
    return f"AttributeItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  def text(self):
    t = f"  <b>{self.name}</b>: {self.value}"
    if self.max_count != -1:
      t += f" ({self.percent}%)"
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
    self.currency_id = 0
    self.market_fee = float(data['market_fee']) / 10**9
    self.royalty_fee = float(data['royalty_fee']) / 10**9
    self.network_fee = float(data['network_fee']) / 10**9
    self.profit = self.price - self.market_fee - self.royalty_fee - self.network_fee
    
    self.usd_price = 0
    self.usd_market_fee = 0
    self.usd_royalty_fee = 0
    self.usd_network_fee = 0
    self.usd_profit = 0
    self.cmc_id()
    self.real_cost()
    
  def __repr__(self):
    return f"PriceItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
  def cmc_id(self):
    if self.currency == 'TON':
      self.currency_id = 11419
    elif self.currency == 'USDT':
      self.currency_id = 825
    elif self.currency == 'NOT':
      self.currency_id = 28850
    else:
      self.currency = 'BTC'
      self.currency_id = 1
  def real_cost(self, value = None):
    price = get_price()[self.currency]
    self.usd_price = self.price * price
    self.usd_market_fee = self.market_fee * price
    self.usd_royalty_fee = self.royalty_fee * price
    self.usd_network_fee = self.network_fee * price
    self.usd_profit = self.profit * price
    
    if value is not None:
      return value * price
  def full_text(self, lang = 'en') -> str:
     text = [f"<b>{translate[lang]['SoldItem'][0]}</b> {self.price_text(self.price)}" if self.price > 0 else "",
          f"  <b>{translate[lang]['SoldItem'][1]}</b> {self.price_text(self.market_fee)}" if self.market_fee > 0 else "",
          f"  <b>{translate[lang]['SoldItem'][2]}</b> {self.price_text(self.royalty_fee)}" if self.royalty_fee > 0 else "",
          f"  <b>{translate[lang]['SoldItem'][3]}</b> {self.price_text(self.network_fee)}" if self.network_fee > 0 else "",
          f"<b>{translate[lang]['SoldItem'][4]}</b> {self.price_text(self.profit)}" if self.profit > 0 else ""]
     clear = [t for t in text if t != ""]
     return '\n'.join(clear) 
  def format_number(self, number: float, dollar=False) -> str:
    form_num = [number,""]
    if number >= 1000**3:
      form_num = [number / 1000**3,"B"]
    elif number >= 1000**2:
      form_num = [number / 1000**2,"M"]
    elif number >= 1000**1:
      form_num = [number / 1000**1,"k"]
    elif not dollar and number <= 1000**-1:
      if number <= 1000**-3:
        form_num = [number / 1000**-3,"n"]
      elif number <= 1000**-2:
        form_num = [number / 1000**-2,"u"]
      elif number <= 1000**-1:
        form_num = [number / 1000**-1,"m"]
    elif number <= 100**-1 and dollar:
        form_num = [number / 1000**-1,"¢"]
    
    if dollar and form_num[1] != "¢":
      form_num[1] = form_num[1] + "$"
    
    if form_num[0] % 100 > 1:
      return f"{form_num[0]:.1f}{form_num[1]}"
    elif form_num[0] % 10 > 1:
      return f"{form_num[0]:.2f}{form_num[1]}"
    elif form_num[1] == "¢":
      return f"{form_num[0]:.0f}{form_num[1]}"
    else:
      return f"{form_num[0]:.3f}{form_num[1]}"
      
  def price_text(self, value) -> str:
    return f'{self.format_number(value)} {self.currency} ({self.format_number(self.real_cost(value=value), True)})' if value is not None and value > 0 else ""

class SoldItem:
  def __init__(self, data):
    self.currency = data['currency']
    self.price = PriceItem({
      'price': int(data['price']),
      'currency': self.currency,
      'market_fee': int(data['price']) * 0.05,
      'royalty_fee': int(data['price']) * 0.05,
      'network_fee': 0,
    })
    self.new = data['newOwnerUser']
    self.old = data['oldOwnerUser']
    self.link = f'https://getgems.io/nft/{data["address"]}'
    
  def details(self, lang = "en", tz = timezone.utc):
    text = [self.price.full_text(lang = lang) + "\n",
            f"<b>{translate[lang]['SoldItem'][5]}</b> {self.new.link_user_text()}",
            f"<b>{translate[lang]['SoldItem'][6]}</b> {self.old.link_user_text()}"]
    clear = [x for x in text if text != ""]
    return '\n'.join(clear) 
  def __repr__(self):
    return f"SoldType({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class AuctionItem:
  def __init__(self, data):
    self.currency = data['currency']
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
      'currency': self.currency,
      'market_fee': price * float(data['marketplaceFeePercent']),
      'royalty_fee': price * float(data['royaltyPercent']),
      'network_fee': int(data['networkFee']),
      })
      
      # price['price'] = data['minBid']
      self.min_bid = PriceItem({
      'price': int(data['minBid']),
      'currency': self.currency,
      'market_fee': int(data['minBid']) * float(data['marketplaceFeePercent']),
      'royalty_fee': int(data['minBid']) * float(data['royaltyPercent']),
      'network_fee': int(data['networkFee']),
      })
      
      # price['price'] = data['maxBid']
      max_bid = int(data['maxBid']) if data['maxBid'] is not None else -1
      self.max_bid = PriceItem({
      'price': max_bid,
      'currency': self.currency,
      'market_fee': max_bid * float(data['marketplaceFeePercent']) if max_bid > 0 else 0,
      'royalty_fee': max_bid * float(data['royaltyPercent']) if max_bid > 0 else 0,
      'network_fee': int(data['networkFee']) if max_bid > 0 else 0,
      })
      
      # self.min_step = data['minStep']
      self.next_bid = PriceItem({
      'price': int(data['minNextBid']),
      'currency': self.currency,
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
      'currency': self.currency,
      'market_fee': price * float(data['marketplaceFeePercent']),
      'royalty_fee': price * float(data['royaltyPercent']),
      'network_fee': 0,
      })
      
      # price['price'] = data['nextBidAmount']
      next_bid = int(data['nextBidAmount']) if 'nextBidAmount' in data and data['nextBidAmount'] is not None else price
      self.next_bid = PriceItem({
      'price': next_bid,
      'currency': self.currency,
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
      'currency': self.currency,
      'market_fee': max_bid * float(data['marketplaceFeePercent']) if max_bid > 0 else 0,
      'royalty_fee': max_bid * float(data['royaltyPercent']) if max_bid > 0 else 0,
      'network_fee': 0,
      })
      
      # price['price'] = data['lastBidAmount']
      self.min_bid = PriceItem({
      'price': price,
      'currency': self.currency,
      'market_fee': price * float(data['marketplaceFeePercent']),
      'royalty_fee': price * float(data['royaltyPercent']),
      'network_fee': 0,
      })
      
      self.nft_owner = data['nftOwnerAddressUser']
      self.min_step = int(data['minStep']) / 100 * price if 'minStep' in data and 1 <=int(data['minStep']) <= 100 \
                      else float(data['minStep']) * price if 'minStep' in data and  1 > int(data['minStep'])\
                      else price - next_bid
      self.finish_at = data['finishAt']
    
  def details(self, lang = "en", tz = timezone.utc):
    text = [self.price.full_text(lang = lang) + "\n",
            f'{self.last_bid.user.link_user_text()} ({format_remaining_time(self.last_bid.time)})' if self.last_bid is not None else "",
            f"<b>{translate[lang]['AuctionItem'][5]}</b> {self.max_bid.price_text(self.max_bid.price)}" if self.max_bid.price > 0 else "",
            f"<b>{translate[lang]['AuctionItem'][6]}</b> {self.next_bid.price_text(self.next_bid.price)}" if self.next_bid.price > 0 else "",
            f"<b>{translate[lang]['AuctionItem'][7]}</b> {self.next_bid.price_text(self.min_step)}" if self.min_step > 0 else "",
            f"<b>{translate[lang]['AuctionItem'][8]}</b> {number_to_date(self.finish_at, tz)} ({format_remaining_time(self.finish_at)})"]
    clear = [x for x in text if text != ""]
    return '\n'.join(clear) 
  def __repr__(self):
    return f"BidItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"

class SaleItem:
  def __init__(self, data):
    self.currency = 'TON'
    self.nft_owner = data['nftOwnerAddressUser']
    self.link = f'https://getgems.io/nft/{data["address"]}'
    self.price = PriceItem({
      'price': int(data['fullPrice']),
      'currency': self.currency,
      'market_fee': int(data['marketplaceFee']),
      'royalty_fee': int(data['royaltyAmount']),
      'network_fee': int(data['networkFee']),
      })
    
  def details(self, lang="en", tz = timezone.utc):
    text = [self.price.full_text(lang = lang) + "\n",
            f"<b>{translate[lang]['SaleItem'][0]}</b> {self.nft_owner.link_user_text()}"]
    clear = [x for x in text if text != ""]
    return '\n'.join(clear) 
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
    if data['sale']:
      self.marketplace = data['sale'][0]
      self.status = data['sale'][1]
      self.sale = data['sale'][2]
    else:
      self.marketplace = MarketplaceType.Getgems
      self.status = NftStatusType.NotForSale
      self.sale = None
  def get_content_url(self, original = True):
    if self.content is not None and original and self.content.original is not None: 
      return self.content.original
    else:
      return self.content.get_url()
    
  def notify_text(self, lang="en", tz = timezone.utc):
    header = f'<b>🖼 "{self.name}"</b>' if not self.history \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][0]}</b>' if self.history.type == HistoryType.PutUpForSale \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][1]}</b>' if self.history.type == HistoryType.Sold \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][2]}</b>' if self.history.type == HistoryType.PutUpForAuction \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][3]}</b>' if self.history.type == HistoryType.Mint \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][4]}</b>' if self.history.type == HistoryType.Burn \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][5]}</b>' if self.history.type == HistoryType.CancelSale \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][6]}</b>' if self.history.type == HistoryType.CancelAuction \
            else f'<b>🖼 "{self.name}" {translate[lang]["NftItem"][7]}</b>' if self.history.type == HistoryType.Transfer \
            else f'<b>🖼 "{self.name}"</b>' if self.history.type == HistoryType.NotForSale \
            else f'<i><b>{translate[lang]["NftItem"][8]} "{self.name}" </b></i>'
            
    body = "\n\n" + self.sale.details(tz = tz, lang = lang) if self.sale is not None else ""
    
    unique = f"<b>{translate[lang]['NftItem'][10]}</b> {self.rarity}/{self.collection.items_count}" if self.collection.isRarity and self.rarity is not None else ""
    likes = f"<b>{translate[lang]['NftItem'][11]}</b> {self.likes} ❤️" if self.likes is not None else ""
    
    attribs = [unique, likes]
    if len(self.attributes) != 0:
      attribs.append(f"<b>{translate[lang]['NftItem'][12]} ({len(self.attributes)})</b>")
      for i in self.attributes:
        attribs.append(i.text())
    attribs = "\n\n" + '\n'.join([x for x in attribs if x != ""]) if len(attribs) != 0 else ""
    
    footer = ("\n\n" + f"<a href=\"{self.owner.get_link(UserLinkType.Tonviewer)}\">{translate[lang]['NftItem'][13]}</a>" +
              f" | <a href=\"{self.owner.get_link(UserLinkType.Getgems)}\">{translate[lang]['NftItem'][14]}</a>")
    
    if self.owner.telegram != "":
      footer += f" | <a href=\"{self.owner.get_link(UserLinkType.Telegram)}\">{translate[lang]['NftItem'][15]}</a>"
    tx_time = "\n" + f"<b>{translate[lang]['NftItem'][16]}</b> {number_to_date(self.history.time, tz)}" if self.history is not None else ""
    
    return f'{header}{body}{attribs}{footer}{tx_time}'
  def __repr__(self):
      return f"NftItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"



# get-funcs to scratch data from Getgems GraphQL API
async def get_user_info(session:aiohttp.ClientSession, user_address: str) -> UserItem:
    query = queries['get_user_info']
    variables = {
        "address": user_address
    }

    data = await get_responce(session,json_data={'query': query, 'variables': variables})
    if data is None or data['data']['userByAddress'] is None or len(data['data']['userByAddress']) == 0:
        variables = {
            "address": address_converter(user_address, AddressType.Unbouncable)
        }
        data = await get_responce(session,json_data={'query': query, 'variables': variables})
        if data is None or data['data']['userByAddress'] is None or len(data['data']['userByAddress']) == 0:
            data = {
                "data": {
                    "userByAddress": {
                        "wallet": user_address,
                        "telegram": {"hasTelegram": False},
                        "name": user_address,
                        "lang": "en",
                        "socialLinks": []
                    }
                }
            }
    return UserItem(data['data']['userByAddress'])
  
async def get_new_history(session:aiohttp.ClientSession, senders_data: tuple, TON_API, first=10) -> list[HistoryItem]:
    query = queries['nft_collection_history']
    variables = {
        "collectionAddress": senders_data[0],
        "first": first,
    }

    all_items = []
    last_time = senders_data[2]
    log_text = f"Items in history (last timestamp: {senders_data[2]}):\n"
    data = await get_responce(session, json_data={'query': query, 'variables': variables})
    if data is None:
        return []

    nft_items = data['data']['historyCollectionNftItems']['items']
    tasks = []

    for item in sorted(nft_items, key=lambda x: x['time'], reverse=True):
        if item['typeData']['historyType'] == 'Sold' or item['typeData']['historyType'] == 'Transfer':
            tasks.append((item, get_user_info(session, item['typeData']['newOwner']), get_user_info(session, item['typeData']['oldOwner'])))

    results = await asyncio.gather(*[task[1] for task in tasks], *[task[2] for task in tasks])

    for index, item in enumerate(tasks):
        item[0]['typeData']['newOwnerUser'] = results[index]
        item[0]['typeData']['oldOwnerUser'] = results[index + len(tasks)]

        if 'currency' not in item[0]['typeData']:
            item[0]['typeData']['currency'] = 'TON'

        if item[0]['time'] > senders_data[2]:
            history = HistoryItem(item[0])
            all_items.append(history)
            last_time = senders_data[2]
            log_text += str(history) + "\n"

    senders_data[2] = last_time
    update_senders_data(senders_data)
    logger.info(log_text)
    return all_items

async def get_nft_owner(session:aiohttp.ClientSession, nft_address: str) -> UserItem:
    query = queries['get_nft_owner']
    variables = {
        "address": nft_address,
        "first": 1
    }

    data = await get_responce(session,json_data={'query': query, 'variables': variables})
    if data is None:
        return None
    return UserItem(data['data']['reactionsNft']['nft']['owner'])

async def get_sale_info(session:aiohttp.ClientSession, history, first=1):
    query_native = queries['get_sale_info']['native']
    query_extend = queries['get_sale_info']['extend']
    
    if history is str and address_converter(history):
      data = {
        "time": now(),
        "typedata":{
          "historyType": "NotForSale"
        },
        "nft":{
          "name":"",
          "address":address_converter(history, AddressType.Bouncable),
        },
        "collectionAddress": ""
      }
      history = HistoryItem(data)
    else:
      return
    
    variables = {
        "address": history.address,
        "first": first
    }
    
    typeofsale = None
    sale = None
    nftstatus = NftStatusType.NotForSale
    currency = history.sold.currency if history.sold is not None else "TON"
    
    owner_task = asyncio.create_task(get_nft_owner(session, history.address))
    responce_native_task = asyncio.create_task(get_responce(session, json_data={'query': query_native, 'variables': variables}))

    owner = await owner_task
    responce_native_data = await responce_native_task
    native_data = responce_native_data['data']['reactionsNft']['nft']['sale']

    if native_data is not None and len(native_data) != 0:
        if native_data['__typename'] == 'NftSaleFixPrice':
            typeofsale = MarketplaceType.Getgems
            nftstatus = NftStatusType.ForSale
            native_data['nftOwnerAddressUser'] = owner
            native_data['type'] = typeofsale
            native_data['currency'] = currency
            native_data['status'] = nftstatus
            native_data['address'] = history.address
            sale = SaleItem(native_data)
        elif native_data['__typename'] == 'NftSaleAuction':
            typeofsale = MarketplaceType.Other
            nftstatus = NftStatusType.ForAuction
            native_data['type'] = typeofsale
            native_data['status'] = nftstatus
            native_data['currency'] = currency
            native_data['nftOwnerAddressUser'] = owner
            native_data['address'] = history.address
            if 'lastBidUser' in native_data and native_data['lastBidUser'] is not None:
                native_data['lastBidUser'] = await get_user_info(session, native_data['lastBidUser']['wallet'])
                native_data['bid'] = BidItem({'lastBidAddress': native_data['lastBidUser'], 'lastBidAt': native_data['lastBidAt']}) if 'lastBidUser' in native_data and native_data['lastBidUser'] is not None else None
            else:
                native_data['bid'] = None
            sale = AuctionItem(native_data)
    else:
        responce_extended_task = asyncio.create_task(get_responce(session, json_data={'query': query_extend, 'variables': variables}))
        responce_extended_data = await responce_extended_task
        extended_data = responce_extended_data['data']['reactionsNft']['nft']['sale']
        if extended_data is not None and len(extended_data) != 0:
            if extended_data['__typename'] == 'NftSaleFixPriceDisintar':
                typeofsale = MarketplaceType.Getgems
                nftstatus = NftStatusType.ForSale
                extended_data['type'] = typeofsale
                extended_data['currency'] = currency
                extended_data['status'] = nftstatus
                extended_data['nftOwnerAddressUser'] = owner
                extended_data['address'] = history.address
                sale = SaleItem(extended_data)
            elif extended_data['__typename'] == 'TelemintAuction':
                typeofsale = MarketplaceType.Other
                nftstatus = NftStatusType.ForAuction
                extended_data['type'] = typeofsale
                extended_data['status'] = nftstatus
                extended_data['currency'] = currency
                extended_data['nftOwnerAddressUser'] = owner
                extended_data['address'] = history.address
                if 'lastBidUser' in extended_data and extended_data['lastBidUser'] is not None:
                    extended_data['lastBidUser'] = await get_user_info(session, extended_data['lastBidUser']['wallet'])
                    extended_data['bid'] = BidItem({'lastBidAddress': extended_data['lastBidUser'], 'lastBidAt': extended_data['lastBidAt']}) if 'lastBidUser' in extended_data and extended_data['lastBidUser'] is not None else None
                else:
                    extended_data['bid'] = None
                sale = AuctionItem(extended_data)
        else:
            if history.sold is not None:
                sale = history.sold

    return [typeofsale, nftstatus, sale, history]

async def get_nft_info(session:aiohttp.ClientSession, 
                       history: HistoryItem|str, 
                       first=1, width=1000, height=1000, 
                       notloadedcontent=json_data['local']['NotLoaded'], proxy=True) -> NftItem:
  
    query = queries['get_nft_info']
    json_data = {
        "query": query,
        "variables": {
            "address": history.address if isinstance(history, HistoryItem) else history,
            "first": first,
            "width": width,
            "height": height
        }
    }

    responce_task = asyncio.create_task(get_responce(session, json_data, proxy=False))
    sale_info_task = asyncio.create_task(get_sale_info(session, history))

    responce = await responce_task
    if responce is None:
        return None
    
    data = responce['data']['reactionsNft']['nft']
    data['sale'] = await sale_info_task
    data['history'] = data['sale'][3] if data['sale'] is not None else None
    data['content']['notLoadedContent'] = notloadedcontent
    
    nft = NftItem(data)
    logger.info(f"NFT info: {nft}")
    
    return nft

async def get_collection_info(session:aiohttp.ClientSession, collection_address: str) -> CollectionItem:
    query = queries['get_collection_info']
    variables = {
        "address": collection_address
    }

    data = await get_responce(session, json_data={"query": query, "variables": variables})
    if data is None:
        return None
    data = data['data']['nftCollectionByAddress']
    logger.info("Collection info: " + str(data))
    return CollectionItem(data)



# other funcs
async def get_responce(session: aiohttp.ClientSession, json_data: dict, tries: int = max_retries, sleep: int = initial_sleep, proxy=True) -> dict | None:
    error = None
    for i in range(tries + 1):
        if i > 0:
            logger.info(f"Retry to get_response number {i} after {sleep} seconds")
        try:
          async with aiohttp.ClientSession() as session:
            async with semaphore:  # Ограничение параллелизма
              proxy = get_proxy() if proxy else None
              async with session.post(api_url, json=json_data, proxy=proxy) as response:
                  response.raise_for_status()
                  data = await response.json()
                  if 'errors' in data:
                      logger.error("Произошла ошибка:")
                      logger.error(data['errors'])
                      return None
                  return data
        except (aiohttp.ClientError, aiohttp.ClientResponseError, asyncio.TimeoutError) as e:
            await asyncio.sleep(sleep)
            logger.error(f"Произошла ошибка: {e}. Следующая попытка через {sleep} сек.")
            error = e
            sleep *= 2  # Увеличиваем интервал ожидания (backoff strategy)
            continue
    logger.error(f"Ошибка при выполнении запроса: {error}")
    return None

async def fetch_data(json_data: dict) -> dict | None:
    async with aiohttp.ClientSession() as session:
        return await get_responce(session, json_data)
  
async def tonapi_get_data(key, address, tries=3, sleep=3) -> dict | None:
    for i in range(tries + 1):
        if i > 0:
            logger.info(f"Retry to get_response number {i}")
        try:
            client = AsyncTonapi(key)
            nft = await client.nft.get_item_by_address(address)
            await client.close()
            if nft is None:
                raise Exception(f"tonapi_get_data: can't find item with address {address}")
            return nft
        except Exception as e:
            logger.error(f"tonapi_get_data: {e}")
            await asyncio.sleep(sleep)
    return None

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
        logger.error(f"Error converting address: {e}")
        return  

def short_address(address) -> str:
  return f"{address_converter(address)[:4]}...{address_converter(address)[-4:]}"

def coinmarketcap_price(cmc_api, ids) -> float:
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
  
  response = requests.get(url, headers=headers, params=parameters)
  
  if response.status_code == 200:
    prices = {}
    data = response.json()
    for id in ids:
      try:
        name = data['data'][str(id)]['symbol']
        price = data['data'][str(id)]['quote']['USD']['price']
        logger.info(f"The current price of {name} ({id}) in USD is: ${price:.2f}")
        prices[id] = [price, name]
      except KeyError:
        logger.error(f"Data for id{id} not found in the response.")
        return None
    return prices
  else:
    logger.error(f"Error: {response.status_code}, {response.text}")
    return None
  
def get_proxy():
  proxy = get_random_proxy()
  if proxy:
    link = proxy[0]  
    logger.info(f"Using proxy: {link.split('@')[-1]}")
    return link
  return None
