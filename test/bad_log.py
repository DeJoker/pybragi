from pybragi.base import log
import logging
logging.info("this")

body = b'{"messages":[{"content":"\xe4\xbb\x8b\xe7\xbb\x8d\xe4\xb8\x80\xe4\xb8\x8b\xe5\x8c\x97\xe4\xba\xac","role":"user"}],"model":"qwen3_235b_0419_25k","frequency_penalty":0.0,"max_tokens":2048,"stream":true,"temperature":0.8,"top_p":0.8,"seed":0,"mid":10086,"timstamp":1747102711,"timstamp2":1747102711,"request_id":"1120189090","repetition_penalty":1.1,"top_k":40}'
try:
    body_str = body.decode('utf-8')
    logging.info(f"body: {body_str}")
except UnicodeDecodeError:
    # 如果解码失败，仍然记录原始bytes
    logging.info(f"body: {body}")




# 是numpy的bug  numpy>=1.23.5 可解决   是1.22.x的问题
# https://github.com/numpy/numpy/issues/24213

# 1.8.0之前日志设定有误 pip install faiss-cpu==1.8.0   其实是依赖的numpy导致的问题
# https://github.com/facebookresearch/faiss/blob/v1.8.0/faiss/python/loader.py
# https://github.com/facebookresearch/faiss/blob/v1.7.3/faiss/python/loader.py

import faiss
log.reset_logging()
logging.info("this")



