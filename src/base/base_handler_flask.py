
from datetime import datetime
from werkzeug import serving
from flask import jsonify, Blueprint, request, current_app
from flask import Flask

parent_log_request = serving.WSGIRequestHandler.log_request
def log_request(self, *args, **kwargs):
    if self.path == '/healthcheck' or self.path == '/metrics':
        return
    parent_log_request(self, *args, **kwargs)

# 不输出healthcheck 和 metrics 请求的打印
def filter_healthcheck_logs():
    serving.WSGIRequestHandler.log_request = log_request


base = Blueprint('base', __name__)
@base.route("/healthcheck", methods=['GET'])
def healthcheck():
    now = datetime.now()
    resp = jsonify(ret=1, errcode=1,
                   data={"timestamp": int(now.timestamp()), "timestamp-str": now.strftime("%Y-%m-%d %H:%M:%S")})
    return resp

def create_app():
    _app = Flask(__name__)
    filter_healthcheck_logs()
    _app.register_blueprint(base)
    return _app

