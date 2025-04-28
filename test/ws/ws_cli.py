#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import uuid

import requests
from pybragi.base import log
import logging
import argparse
import json
import os
import sys
import threading
import time
import websocket # pip install websocket-client==1.8.0
import signal
from datetime import datetime


class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.running = False
        self.connected = False

    def on_message(self, ws, message):
        if isinstance(message, bytes):
            logging.info(f"binary message, length: {len(message)} bytes")
        else:
            try:
                data = json.loads(message)
                logging.info(f"json message: {json.dumps(data, ensure_ascii=False, indent=2)}")
            except json.JSONDecodeError:
                logging.info(f"message: {message}")

    def on_error(self, ws, error):
        logging.info(f"error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.info(f"disconnected (status: {close_status_code}, msg: {close_msg})")
        self.connected = False

    def on_open(self, ws):
        logging.info(f"connected to {self.url}")
        self.connected = True

    def connect(self):
        # websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.running = True
        
        self.client_thread = threading.Thread(target=self.ws.run_forever)
        self.client_thread.daemon = True
        self.client_thread.start()
        
        timeout = 5
        start_time = time.perf_counter()
        while not self.connected and time.perf_counter() - start_time < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            logging.info(f"timeout {timeout}s: cannot connect to {self.url}")
            return False
        return True

    def disconnect(self):
        if self.ws:
            self.ws.close()
        self.running = False
        logging.info("disconnected")

    def send_json(self, data: dict):
        if not self.connected:
            logging.info("error: not connected")
            return False
        
        try:
            message = json.dumps(data)
            
            logging.info(f"send: {message}")
            self.ws.send(message)
            return True
        except Exception as e:
            logging.info(f"error: {e}")
            return False

    def send_file(self, data):
        if not self.connected:
            logging.info("error: not connected")
            return False
        
        try:
            logging.info(f"send file: {len(data)} bytes")
            self.ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
            return True
        except Exception as e:
            logging.info(f"error: {e}")
            return False


def mock_json():
    return {
        "name": "test",
        "request_id": f"{int(time.time())}-{uuid.uuid4()}",
        "data": f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}-{uuid.uuid4()}"
    }


def main(url="ws://localhost:8888/ws", audio_urls=[]):
    client = WebSocketClient(url)
    client.connect()
    while client.running:
        client.send_json(mock_json())
        time.sleep(random.randint(100, 300)/1000)

        resp = requests.get(audio_urls[random.randint(0, len(audio_urls) - 1)])
        client.send_file(resp.content)
        for pos in range(0, len(resp.content), 1024):
            client.send_file(resp.content[pos:pos+1024])
            time.sleep(random.randint(100, 300)/1000)


    


if __name__ == "__main__":
    audio_urls = []
    with open("/mnt/c/Dev/self/self_doc/最右/day/2025/2025-02/audio-list.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            audio_urls.append(line)
    
    main(audio_urls=audio_urls)
