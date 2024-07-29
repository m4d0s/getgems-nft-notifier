import requests
import pycoingecko
from pycoingecko import CoinGeckoAPI
import logging

def ton_price() -> float:

        cg = CoinGeckoAPI()
        response = cg.get_price(ids=['bitcoin', 'ethereum', 'solana' ,'toncoin'], vs_currencies=['usd', 'eur'])
        print(response)
    
ton_price()