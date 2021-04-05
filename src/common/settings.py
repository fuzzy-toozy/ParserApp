import json
import os

SECRET_KEY = "89da0d2c-8d16-4b99-964f-21a07c479587-fisting-is-300$"
config_name = "parser.conf"
with open("parser.conf", "r") as f:
    config = json.loads(f.read())


def get_root_dir():
    return config["RootDir"]


def get_config():
    return config


PARSERS_DIR = os.path.join(get_root_dir(), "parsers")

