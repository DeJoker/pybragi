import argparse
import yaml
from typing import Any


class AttrDict(dict):
    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def __getattr__(self, key):
        return self[key]

def dict_to_namespace(config_dict):
    args = argparse.Namespace()
    for key, value in config_dict.items():
        setattr(args, key, value)
    return args


def recursive_convert(attr_dict):
    if not isinstance(attr_dict, dict):
        return attr_dict
    obj_dict = AttrDict()
    for key, value in attr_dict.items():
        obj_dict[key] = recursive_convert(value)
    return obj_dict


def parse_config(cfg_file):
    with open(cfg_file, "r") as f:
        attr_dict_conf = AttrDict(yaml.load(f, Loader=yaml.Loader))
    obj_dict_conf = recursive_convert(attr_dict_conf)
    return obj_dict_conf
