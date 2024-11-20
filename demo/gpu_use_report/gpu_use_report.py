import os
import requests
from pybragi.base import log
import logging
from pydantic import BaseModel
from sortedcontainers import SortedDict
from pybragi.base import gpu_detect

import time
import hmac
import hashlib
import base64
import urllib.parse

machines = [
    "beijing-aigc-gpt-gpu01",
    "beijing-aigc-gpt-gpu02",
    "beijing-aigc-gpt-gpu03",
    "beijing-aigc-gpt-gpu07",
    "xljn-aigc-gpt-t01002",
    "xljn-aigc-gpt-t01003",
    "shal-zy-aigc-gpt-gpu01",
]

class MetricsStat(BaseModel):
    Gpu: str = ""
    # 以下为90时间分位的数值 而不是数值vector的90分位
    UtiltyAvg: float = 0.0
    MemoryAvg: float = 0.0
    MemoryP50: float = 0.0

    def pretty_print(self):
        return f"gpu:{self.Gpu} 平均使用率:{self.UtiltyAvg:.3f}% " +\
                f"平均显存占用:{self.MemoryAvg/1024:.3f}GB 50时间分位显存占用:{self.MemoryP50/1024:.3f}GB"


def aliding_host():
    timestamp = str(round(time.time() * 1000))
    DING_SECRET = os.environ.get("DING_SECRET", "")
    secret_enc = DING_SECRET.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, DING_SECRET)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

    DING_ACCESS = os.environ.get("DING_ACCESS", "")
    url = f"https://oapi.dingtalk.com/robot/send?access_token={DING_ACCESS}" +\
          f"&timestamp={timestamp}&sign={sign}"
    logging.info(url)
    return url


def dingcall(title, text):
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text
        },
        "at": {
            # "atMobiles": at_list, "isAtAll": isAtAll
        },
    }
    url = aliding_host()

    headers = {'Content-Type': 'application/json;charset=UTF-8'}
    result = requests.post(url, json=data, headers=headers)
    if result.json()['errcode'] == 0:
        print('发送成功')
    else:
        print('发送失败')



def report_all():
    for machine in machines:
        uitlity_avg = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{Hostname="{machine}"}}[7d])'
        memory_avg = f'avg_over_time(DCGM_FI_DEV_FB_USED{{Hostname="{machine}"}}[7d])'
        memory_p90 = f'quantile_over_time(0.5, DCGM_FI_DEV_FB_USED{{Hostname="{machine}"}}[7d])'

        if machine.startswith("shal") or machine.startswith("xljn"):
            uitlity_avg = f'avg_over_time(DCGM_FI_DEV_GPU_UTIL{{host="{machine}"}}[7d])'
            memory_avg = f'avg_over_time(DCGM_FI_DEV_FB_USED{{host="{machine}"}}[7d])'
            memory_p90 = f'quantile_over_time(0.5, DCGM_FI_DEV_FB_USED{{host="{machine}"}}[7d])'


        current = SortedDict()
        res = gpu_detect.get_gpu_utilty_prometheus(uitlity_avg)
        result = res.get("data", {}).get("result", [])
        for res in result:
            gpu = res.get("metric", {}).get("gpu", -1)
            uitlityAvg = float(res.get("value", [0, ''])[1])
            current[gpu] = MetricsStat(Gpu=gpu, UtiltyAvg=uitlityAvg)
        
        res = gpu_detect.get_gpu_utilty_prometheus(memory_avg)
        result = res.get("data", {}).get("result", [])
        for res in result:
            gpu = res.get("metric", {}).get("gpu", -1)
            memoryAvg = float(res.get("value", [0, ''])[1])
            current[gpu].MemoryAvg = memoryAvg
        
        res = gpu_detect.get_gpu_utilty_prometheus(memory_p90)
        result = res.get("data", {}).get("result", [])
        for res in result:
            gpu = res.get("metric", {}).get("gpu", -1)
            memoryP50 = float(res.get("value", [0, ''])[1])
            current[gpu].MemoryP50 = memoryP50
        
        logging.info(f"{machine}")
        dingmsg = f"## {machine} 过去七天资源使用情况 \n"
        for _,stat in current.items():
            logging.info(f"{stat.pretty_print()}")
            dingmsg += f"> {stat.pretty_print()}  \n"
        dingcall(machine, dingmsg)



if __name__ == "__main__":
    text = "# 一级标题 \n" + "## 二级标题 \n" + "> 引用文本  \n" + "**加粗**  \n" + "*斜体*  \n" + "<font color=\"#FF0000\">颜色</font> \n" + "[百度链接](https://www.baidu.com)\n\n\n\n"
    # dingcall("过去七天使用情况", text)

    report_all()

