import requests
import asyncio
import sqlite3
import json
import time
import datetime
import asyncio
import TonTools
import logging
import pytonapi
from enum import Enum
from tonsdk.contract import Address

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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

class HistoryItem:
    def __init__(self, data, TON_API):
        self.name = data['nft']['name']
        self.address = data['address']
        self.collection = data['collectionAddress']
        self.collection_name = data['CollectionName']
        self.time = data['time']
        self.verify= data['verify']
        self.getgems = data['getgems']
        if self.verify:
          self.verified_by= data['verified_by']
        else:
          self.verified_by= []
        self.social = data["SocialLinks"]
        try:
          self.price = data['typeData']['price'] / (10**9)
        except:
          self.price = 0
          
        try:
            self.type = HistoryType[data['typeData']['historyType']]
        except KeyError:
            self.type = None
            
    def __repr__(self):
        return f"HistoryItem({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"
        
class SocialLinks:
    def __init__(self, data):
      self.links = []
      for link in data:
        if link.startswith('https://twitter.com/') or link.startswith('https://www.twitter.com/') or\
          link.startswith('https://www.x.com/') or link.startswith('https://www.x.com/'):
          self.links.append((link, 'Twitter'))
        elif link.startswith('https://t.me/') or link.startswith('https://telegram.me/'):
          self.links.append((link, f'Telegram : @{link.split("/")[3].split("/")[0]}'))
        elif link.startswith('https://youtube.com/') or link.startswith('https://www.youtube.com/'):
          self.links.append((link, 'Youtube'))
        elif link.startswith('https://discord.com/') or link.startswith('https://www.discord.com/'):
          self.links.append((link, 'Discord'))
        elif link.startswith('https://vk.com/') or link.startswith('https://www.vk.com/'):
          self.links.append((link, 'VK'))
        elif link.startswith('https://instagram.com/') or link.startswith('https://www.instagram.com/'):
          self.links.append((link, 'Instagram'))
        else:
          self.links.append((link, link.split('/')[2].split('.')[0].capitalize().replace('.', ' ')))
    def __repr__(self):
        return f"SocialLinks({self.links})"
      
async def get_collection_info(collection_address: str):
    query = """query NftCollectionByAddress($address: String!) {
  nftCollectionByAddress(address: $address) {
    name
    socialLinks
    address
  }
}"""

    variables = {
        "address": collection_address
    }

    url = 'https://api.getgems.io/graphql'

    response = requests.post(url, json={'query': query, 'variables': variables})
    if response.status_code != 200:
        print("Ошибка при выполнении запроса. Код ошибки:", response.status_code)
        return None

    data = response.json()
    if 'errors' in data:
        print("Произошла ошибка:")
        print(data['errors'])
        return None

    data = data['data']['nftCollectionByAddress']
    
    return data

async def nft_collection_history(collection_address: str, TON_API, first = 3):
    query = """query HistoryCollectionSales($collectionAddress: String!, $first: Int!) {
  historyCollectionNftItems(collectionAddress: $collectionAddress, first: $first) {
    items {
      address
      collectionAddress
      time
      typeData {
        ... on HistoryTypeMint {
          type
          historyType
        }
        ... on HistoryTypeTransfer {
          type
          historyType
          oldOwner
          newOwner
        }
        ... on HistoryTypeCancelSale {
          type
          historyType
          owner
          price
        }
        ... on HistoryTypeSold {
          type
          historyType
          oldOwner
          newOwner
          price
          rejectFromGlobalTop
        }
        ... on HistoryTypePutUpForSale {
          type
          historyType
          owner
          price
        }
        ... on HistoryTypePutUpForAuction {
          type
          historyType
          owner
        }
        ... on HistoryTypeCancelAuction {
          type
          historyType
          owner
        }
        ... on HistoryTypeBurn {
          type
          historyType
          oldOwner
          newOwner
        }
      }
      nft {
        address
        name
      }
    }
  }
}"""

    variables = {
        "collectionAddress": collection_address,
        "first": first,
    }

    url = 'https://api.getgems.io/graphql'
    all_items = []

    response = requests.post(url, json={'query': query, 'variables': variables})
    if response.status_code != 200:
        print("Ошибка при выполнении запроса. Код ошибки:", response.status_code)
        return None

    data = response.json()
    if 'errors' in data:
        print("Произошла ошибка:")
        print(data['errors'])
        return None
      
    info = await get_collection_info(collection_address=collection_address)

    nft_items = data['data']['historyCollectionNftItems']['items']
    for item in nft_items:
        item['CollectionName'] = info['name']
        item["SocialLinks"] = SocialLinks(info['socialLinks'])
        item['getgems'] = f'https://getgems.io/collection/{collection_address}/{item["address"]}'
        
        for i in range(3+1):
          tonapi_data = await tonapi_get_data(TON_API, item['address'])
          if i == 3:
            print("TonAPI can't fetch data for", item['address'])
          if tonapi_data is None:
            continue
          #print(tonapi_data)
          try:
            item['price'] = tonapi_data.sale.price.value
          except AttributeError:
            item['price'] = 0
          try:
            item['verified_by'] = tonapi_data.approved_by
          except AttributeError:
            item['verified_by'] = []   
          try:
            item['verify'] = tonapi_data.verified
          except AttributeError:
            item['verify'] = False
          try:
            item['photo'] = tonapi_data.metadata['image']
          except KeyError:
            item['photo'] = tonapi_data.previews[-1].url
          break
            
        item = HistoryItem(item, TON_API=TON_API)
        all_items.append(item)
    
    return all_items

def separate_history_items(all_items: list[HistoryItem]):
    sold, on_auc, on_sale, other = [],[],[],[]
    for item in all_items:
        if item.type == HistoryType.Sold:
            sold.append(item)
        elif item.type == HistoryType.PutUpForSale:
            on_sale.append(item)
        elif item.type == HistoryType.PutUpForAuction:
            on_auc.append(item)
        else:
            other.append(item)
    
    return {"Sold":sold, "PutUpForSale":on_auc, "PutUpForAuction":on_sale, "Other":other}

async def get_separate_history_items(collection_address:str, TON_API:str, first = 3):
  all = await nft_collection_history(collection_address, TON_API=TON_API, first=first)
  sep = separate_history_items(all)
  return sep

async def tonapi_get_data(key, address):
    try:
        client = pytonapi.AsyncTonapi(key)
        nft = await client.nft.get_item_by_address(address)
        if nft is None:
            raise Exception(f"tonapi_get_data: can't find item with address {address}")
        return nft
    except Exception as e:
        print(f"tonapi_get_data: {e}")
        return None

async def tontools_get_data(key,address):
    client = TonTools.TonCenterClient(key)
    item = TonTools.NftItem(data=address, provider=client)
    await item.update()
    return item
  
def address_converter(address, format:AddressType = AddressType.Bouncable):
    try:
        # Создаем объект Address из входного адреса
        addr = Address(address)
        
        if format == AddressType.Bouncable:
            return addr.to_string(True, True, True)
        elif format == AddressType.Unbouncable:
            return addr.to_string(True, True, False)
        elif format == AddressType.Raw:
            return addr.to_string(False, True, True)
        else:
            raise ValueError("Invalid target format specified. Use 'user_friendly' or 'raw'.")
    except Exception as e:
        return f"Error converting address: {e}"
    