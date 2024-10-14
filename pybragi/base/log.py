#!/usr/bin/env python
# -*- coding:utf-8 -*-
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime
from . import scribe_log

format = "%(levelname)s %(asctime)s.%(msecs)03d [%(process)d-%(threadName)s] (%(funcName)s@%(filename)s:%(lineno)03d) %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(format=format, datefmt=datefmt, level=logging.INFO, handlers=[logging.StreamHandler()])
logging.info(f"init log")


def init_logger(service, file_enabled=False, scribe_category='', file_path='', tag=""):
    fmt = logging.Formatter(fmt=format, datefmt=datefmt)
    logger = logging.getLogger()
    if file_enabled:
        # dir = os.path.join(file_path, service)
        dir = file_path
        try:
            os.makedirs(dir)
        except:
            pass

        filename = os.path.join(dir, service+".log")
        if tag:
            filename = os.path.join(dir, service+"_"+str(tag)+ ".log")

        # logging.handlers.TimedRotatingFileHandler 这样不行
        file_handler = TimedRotatingFileHandler(filename, when='midnight', interval=1, backupCount=21)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    if os.getenv('NODE_IP') and os.getenv('RUN_ENVIRONMENT') == 'k8s':
        host = os.getenv('NODE_IP', '')
        handler = scribe_log.ScribeHandler(host=host, port=9121, category=scribe_category)
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


class IgnoreFilter(logging.Filter):
    def __init__(self, ignore_file, ignore_lineno):
        super().__init__()
        self.ignore_file = ignore_file
        self.ignore_lineno = ignore_lineno

    def filter(self, record):
        return not (record.filename == self.ignore_file and record.lineno == self.ignore_lineno)


class ServiceLoggerHandler(logging.Handler):
    def __init__(self, filename=""):
        self.filename = filename
        if not filename:
            self.filename = os.path.join("logs", "%Y-%m-%d.log")
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        fpath = datetime.now().strftime(self.filename)
        fdir = os.path.dirname(fpath)
        try:
            if not os.path.exists(fdir):
                os.makedirs(fdir)
        except Exception as e:
            print(e)

        try:
            f = open(fpath, 'a')
            f.write(msg)
            f.write("\n")
            f.flush()
            f.close()
        except Exception as e:
            print(e)
