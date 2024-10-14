from typing import Optional
import requests
import traceback
from service.base import time_utils

def post(url, json:dict={}):
    with time_utils.ElapseCtx(f"{url} post:{json}"):
        try:
            return requests.post(url, json=json), None
        except Exception as e:
            traceback.print_exc()
            return None, e


def post2(url, json:dict={}, data=None):
    with time_utils.ElapseCtx(f"{url} post:{json}"):
        try:
            if len(json)>0:
                return requests.post(url, json=json), None
            elif data:
                return requests.post(url, data=data), None
        except Exception as e:
            traceback.print_exc()
            return None, e


        
