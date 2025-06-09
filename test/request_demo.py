import logging
from pybragi.base import time_utils
import requests



resp = requests.get("baidu.com")
logging.info(f"resp: {resp.status_code} {resp.text}")





