
import logging
import os
from io import BytesIO
from datetime import datetime
from pathlib import Path
import oss2
import requests

from pybragi.base import time_utils

internal_endpoint = "oss-cn-shanghai-internal.aliyuncs.com"
endpoint = "oss-cn-shanghai.aliyuncs.com"
bucket_name = "shencha-model-platform"

def upload_wanxiang(file_path, filename=''):
    if not filename:
        filename = Path(file_path).name

    logging.info(f'upload {file_path} to {filename}')

    auth = oss2.Auth(os.getenv("model_platform_ak", ""), os.getenv("model_platform_as", ""))
    bucket = oss2.Bucket(auth, internal_endpoint, bucket_name)

    oss_path = f'aigc/wanxiang/{filename[-4:]}/{filename}'
    exist = bucket.object_exists(oss_path)
    if exist:
        logging.info(f'{oss_path} exist')
        return
    resp = bucket.put_object_from_file(oss_path, file_path)
    logging.info(f'upload to infer_engine/class/{oss_path}')
    resp_info = ", ".join("%s: %s" % item for item in vars(resp).items())
    logging.info(f'{resp_info}')
    return "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/" + oss_path, resp.status == 200


@time_utils.elapsed_time_limit(0.05)
def upload_rvc(bytes: BytesIO, request_id: str):
    auth = oss2.Auth(os.getenv("model_platform_ak", ""), os.getenv("model_platform_as", ""))
    bucket = oss2.Bucket(auth, internal_endpoint, bucket_name)

    oss_path = f'aigc/rvc/{request_id[-4:]}/{request_id}.wav'
    resp = bucket.put_object(oss_path, bytes)
    logging.info(f'upload to infer_engine/class/{oss_path}')
    resp_info = ", ".join("%s: %s" % item for item in vars(resp).items())
    logging.info(f'{resp_info}')
    return "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/" + oss_path, resp.status == 200



if __name__ == '__main__':
    res = requests.get("http://zyvideo101.oss-cn-shanghai.aliyuncs.com/zyad/4e/33/1ce5-cd9e-11ef-bdec-00163e023ce8")
    res = upload_rvc(BytesIO(res.content), 'c')
    print(res)

