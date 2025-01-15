from pybragi.base import log
import logging
logging.info("this")

# 1.8.0之前日志设定有误 pip install faiss-cpu==1.8.0
# https://github.com/numpy/numpy/issues/24213
# https://github.com/facebookresearch/faiss/blob/v1.8.0/faiss/python/loader.py
# https://github.com/facebookresearch/faiss/blob/v1.7.3/faiss/python/loader.py

import faiss
log.setup_logging()
logging.info("this")



