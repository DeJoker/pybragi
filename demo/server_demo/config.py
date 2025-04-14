# -*- coding:utf-8 -*-

import os

class ConfigOnline(object):
    Name = "rvc_infer"
    Port = 23001
    Host = "0.0.0.0"
    Online = True



class ConfigTest(object):
    Name = "rvc_infer"
    Port = 23001
    Host = "0.0.0.0"
    Online = False



Config = ConfigOnline
import os
if "test" in os.getenv('PROJECT_ENV', ''):
    Config = ConfigTest

