
import logging
import os
from io import BytesIO
from datetime import datetime
from pathlib import Path
import oss2

from pybragi.base import time_utils

def upload_wanxiang(file_path, filename=''):
    if not filename:
        filename = Path(file_path).name

    logging.info(f'upload {file_path} to {filename}')

    auth = oss2.Auth(os.getenv("model_platform_ak", ""), os.getenv("model_platform_as", ""))
    bucket = oss2.Bucket(auth, 'oss-cn-shanghai.aliyuncs.com', 'shencha-model-platform')

    oss_path = 'aigc/wanxiang/'+filename
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
    bucket = oss2.Bucket(auth, 'oss-cn-shanghai.aliyuncs.com', 'shencha-model-platform')

    oss_path = f'aigc/rvc/{request_id}.wav'
    resp = bucket.put_object(oss_path, bytes)
    logging.info(f'upload to infer_engine/class/{oss_path}')
    resp_info = ", ".join("%s: %s" % item for item in vars(resp).items())
    logging.info(f'{resp_info}')
    return "https://shencha-model-platform.oss-cn-shanghai.aliyuncs.com/" + oss_path, resp.status == 200