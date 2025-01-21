import aiohttp, asyncio
import numpy as np
import os, io, json
import logging
from PIL import Image
import base64
import requests
import zstd
import traceback
from pybragi.base import time_utils, image_process

@time_utils.elapsed_time_callback()
def upload_zy_img(img_base64):
    temp_url = "http://media-gateway-op.srv.ixiaochuan.cn/op/save_image"
    data = {
        "internal_token": "5b8f785cd50a7d40714ff76d01699688",
        "file_data": img_base64,
        "buss_type": "zuiyou_img"
    }
    response = requests.post(temp_url, json=data)
    logging.info(f"{response.text} {response.status_code}")
    if response.status_code == 200:
        return json.loads(response.text)['data']['id']
    else:
        return -1


def pil_upload(pil_img: Image.Image, test:bool=False):
    img_base64 = image_process.pil2base64(pil_img)
    return upload_novel_img(img_base64, test)

@time_utils.elapsed_time_callback()
def upload_novel_img(img_base64, test=False):
    logging.info(f"upload {len(img_base64)}")
    temp_url = "http://dolphin-media-gateway.srv.wanyaa.com/op/save_image"
    if test:
        temp_url = "http://dolphin-media-gateway.srv.test.wanyaa.com/op/save_image"
    data = {
        "internal_token": "5b8f785cd50a7d40714ff76d01699688",
        "file_data": img_base64,
        "buss_type": "dolphin_img"
    }
    response = requests.post(temp_url, json=data)
    if test:
        logging.info(f"{response.text} {response.status_code}")
    if response.status_code == 200:
        return json.loads(response.text).get("data", {}).get("id", -1)
    else:
        return -1


async def async_upload_zy_img(session :aiohttp.ClientSession, img_base64):
    temp_url = "http://media-gateway.srv.ixiaochuan.cn/op/save_image"
    temp_url = "http://172.16.0.37:8088/op/save_image"
    data = {
        "internal_token": "5b8f785cd50a7d40714ff76d01699688",
        "file_data": img_base64,
        "buss_type": "zuiyou_img"
    }
    async with session.post(temp_url, json=data) as response:
        resp_data = await response.text()
        if response.status == 200:
            return json.loads(resp_data)['data']['id']
        else:
            return -1

async def async_upload_zy_imgs(images):
    async with aiohttp.ClientSession() as session:
        tasks = [async_upload_zy_img(session, image) for image in images]
        # 并发执行所有上传任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(results)
