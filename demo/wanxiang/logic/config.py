# -*- coding:utf-8 -*-

class ConfigOnline(object):
    Name = "clay_effect"
    Port = 30010
    Host = "0.0.0.0"
    LocalHost = "60.217.224.164"
    Batch = 2
    MaxWait = 200  # ms

class ConfigTest(object):
    Name = "clay_effect"
    Port = 30010
    Host = "0.0.0.0"
    LocalHost = "60.217.224.164"


Config = ConfigOnline
import os
if os.getenv('PROJECT_ENV') != "online":
    Config = ConfigTest

