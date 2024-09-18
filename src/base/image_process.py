import random
import aiohttp, asyncio
import numpy as np
import cv2
import os, io, json
import logging
from PIL import Image
import base64
import requests
import zstd
import traceback, inspect
from . import time_utils



def base642pil(base64_str):
    return Image.open(io.BytesIO(base64.b64decode(base64_str)))

@time_utils.elapsed_time_callback()
def pil2base64(pil_img: Image.Image, fmt='JPEG'):
    with io.BytesIO() as output_buffer:
        pil_img.save(output_buffer, format=fmt)
        byte_data = output_buffer.getvalue()
    base64_str = base64.b64encode(byte_data).decode('utf-8')
    return base64_str


def download_byte(url: str):
    try:
        # 其实不用 inspect.currentframe().f_code.co_name 加上特别就可以
        with time_utils.ElapseCtx(f"{url} download"):
            resp = requests.get(url)
            if not (resp.status_code == 200):
                logging.warning(f"{url} error code {resp.status_code} {resp.reason}")
                return None
            return resp.content
    except:
        traceback.print_exc()
        return None

@time_utils.elapsed_time_callback()
def numpy_compress(img_np: np.ndarray):
    cdata = zstd.compress(img_np.tobytes(), 10)
    logging.info(f'byte:{len(img_np)} compress:{len(cdata)} '
                 f'ratio:{round(len(cdata)/len(img_np), 3)}')
    return cdata

@time_utils.elapsed_time_callback()
def numpy_decompress(cdata: bytes, shape=(512, 512, 3), dtype=np.uint8):
    ddata = zstd.decompress(cdata)
    img_np = np.frombuffer(ddata, dtype=dtype).reshape(shape)
    logging.info(f'byte:{len(cdata)} decompress:{len(ddata)} '
                 f'ratio:{round(len(cdata) / len(ddata), 3)}')
    return img_np

@time_utils.elapsed_time_callback()
def img_compress(image: Image.Image, fmt='JPEG'):
    with io.BytesIO() as output_buffer:
        image.save(output_buffer, format=fmt)
        img_byte = output_buffer.getvalue()

    cdata = zstd.compress(img_byte, 10)
    logging.info(f'image:{image.size}  byte:{len(img_byte)} compress:{len(cdata)} '
                 f'ratio:{round(len(cdata)/len(img_byte), 3)}')
    return cdata


@time_utils.elapsed_time_callback()
def img_decompress(cdata: bytes):
    ddata = zstd.decompress(cdata)
    image2 = Image.open(io.BytesIO(ddata))
    logging.info(f'byte:{len(cdata)} decompress:{len(ddata)} image:{image2.size} '
                 f'ratio:{round(len(cdata) / len(ddata), 3)}')
    return image2


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
    img_base64 = pil2base64(pil_img)
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

def HWC3(x):
    assert x.dtype == np.uint8
    if x.ndim == 2:
        x = x[:, :, None]
    assert x.ndim == 3
    H, W, C = x.shape
    assert C == 1 or C == 3 or C == 4
    if C == 3:
        return x
    if C == 1:
        return np.concatenate([x, x, x], axis=2)
    if C == 4:
        color = x[:, :, 0:3].astype(np.float32)
        alpha = x[:, :, 3:4].astype(np.float32) / 255.0
        y = color * alpha + 255.0 * (1.0 - alpha)
        y = y.clip(0, 255).astype(np.uint8)
        return y



# -----------------------------------------------------------------------------


def resize_image(input_image, resolution):
    H, W, C = input_image.shape
    H = float(H)
    W = float(W)
    k = float(resolution) / min(H, W)
    H *= k
    W *= k
    H = int(np.round(H / 64.0)) * 64
    W = int(np.round(W / 64.0)) * 64
    img = cv2.resize(input_image, (W, H), interpolation=cv2.INTER_LANCZOS4 if k > 1 else cv2.INTER_AREA)
    return img


def nms(x, t, s):
    x = cv2.GaussianBlur(x.astype(np.float32), (0, 0), s)

    f1 = np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0]], dtype=np.uint8)
    f2 = np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], dtype=np.uint8)
    f3 = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.uint8)
    f4 = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]], dtype=np.uint8)

    y = np.zeros_like(x)

    for f in [f1, f2, f3, f4]:
        np.putmask(y, cv2.dilate(x, kernel=f) == x, x)

    z = np.zeros_like(y, dtype=np.uint8)
    z[y > t] = 255
    return z


def make_noise_disk(H, W, C, F):
    noise = np.random.uniform(low=0, high=1, size=((H // F) + 2, (W // F) + 2, C))
    noise = cv2.resize(noise, (W + 2 * F, H + 2 * F), interpolation=cv2.INTER_CUBIC)
    noise = noise[F: F + H, F: F + W]
    noise -= np.min(noise)
    noise /= np.max(noise)
    if C == 1:
        noise = noise[:, :, None]
    return noise


def min_max_norm(x):
    x -= np.min(x)
    x /= np.maximum(np.max(x), 1e-5)
    return x


def safe_step(x, step=2):
    y = x.astype(np.float32) * float(step + 1)
    y = y.astype(np.int32).astype(np.float32) / float(step)
    return y


def img2mask(img, H, W, low=10, high=90):
    assert img.ndim == 3 or img.ndim == 2
    assert img.dtype == np.uint8

    if img.ndim == 3:
        y = img[:, :, random.randrange(0, img.shape[2])]
    else:
        y = img

    y = cv2.resize(y, (W, H), interpolation=cv2.INTER_CUBIC)

    if random.uniform(0, 1) < 0.5:
        y = 255 - y

    return y < np.percentile(y, random.randrange(low, high))
