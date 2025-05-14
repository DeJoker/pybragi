#!/usr/bin/env python
# -*- coding:utf-8 -*-
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime

format = "%(levelname)s %(asctime)s.%(msecs)03d [%(process)d-%(threadName)s] (%(funcName)s@%(filename)s:%(lineno)03d) %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(fmt=format, datefmt=datefmt))

logging.basicConfig(format=format, datefmt=datefmt, level=logging.INFO, force=True, handlers=[logging.StreamHandler()])

from pybragi import __version__
logging.info(f"init log. pybragi version: {__version__}")

def use_loguru():
    from loguru import logger
    import sys
    import logging

    # Remove default logger
    logger.remove()

    # Add our custom formatter
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> {time:YYYY-MM-DD HH:mm:ss.SSS} [{process}-{thread.name}] ({function}@{file}:{line}) {message}",
        level="INFO"
    )

    # Create class to intercept standard logging
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    def setup_logging():
        # Remove existing handlers
        logging.root.handlers = []
        
        # Add our interceptor
        logging.root.addHandler(InterceptHandler())
        
        # Set minimum logging level
        logging.root.setLevel(logging.INFO)

    # Initial setup
    setup_logging()


def reset_logging():
    if logging.root.handlers:
        print(f"logging already init. reset all")
        for handler in logging.root.handlers[:]:
            print(f"{handler.name}")
            logging.root.removeHandler(handler)
            handler.close()
            
    for logger_name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            # Remove handlers from each logger
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            # Optionally, you can also set the level to NOTSET to reset the logger level
            logger.setLevel(logging.NOTSET)


    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)


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
        from . import scribe_log
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
