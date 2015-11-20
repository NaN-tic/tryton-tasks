import json
import requests
from os import getenv
from os import path

import pprint
pp = pprint.PrettyPrinter(indent=4)

CONFIG_DIR = '~/'
CONFIG_FILE = '.bitbucket.json'

config = dict()

config_path = path.expanduser(CONFIG_DIR)
config_file = path.join(config_path, CONFIG_FILE)

if path.isfile(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)


def get_auth():
    return config.get('username'), config.get('password')


auth = get_auth()


def post(url, data):
    headers = {'Content-Type': 'application/json'}

    payload = json.dumps(data)
    r = requests.post(url, data=payload, headers=headers, auth=auth)
    return r.json()


def get(url, data):
    headers = {'Content-Type': 'application/json'}
    payload = json.dumps(data)
    r = requests.get(url, data=payload, headers=headers, auth=auth)
    return r.json()


def prettyprint(data):
    pp.pprint(data)


