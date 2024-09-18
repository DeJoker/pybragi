
import logging
import json
import time
import copy
from wanxiang.logic.config import Config
from base import errcode
from base.metrics import PrometheusMixIn, get_metrics_manager

from base import time_utils, errcode
from wanxiang.logic import infer

class Generator(PrometheusMixIn):
    required_fields = ["prompt", "request_id"]  # 必填字段列表

    # 不需要并发接口不加 run_on_executor
    def post(self):
        logging.info(f"{self.request.body.decode('unicode_escape')}")
        task = json.loads(self.request.body)
        for field in self.required_fields:
            if field not in task:
                self.finish(
                    {"ret": -1, "msg": f"Missing required field: {field}"}
                )  # 返回错误响应
                return
            if not task.get(field):
                return self.write({"ret":-1, "msg":f"{field} required"})

        resp_data = {
            "request_id": task.get("request_id", ""),
            "ext": task.get("ext", {})
        }
        
        task['ct'] = time.time()
        task['status'] = errcode.new_status

        if not infer.get_engine().comfyui_valid:
            return self.write({"ret":-1, "msg":"comfyui not ok"})

        result = infer.process_one(task)
        if isinstance(result, list):
            resp_data["status"] = 1
            resp_data["final_imgurls"] = result
        else:
            resp_data["status"] = -1
            resp_data["err_str"] = result

        return self.write({"ret":1, "data":resp_data})
    
