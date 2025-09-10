# -*- encoding: utf-8 -*-
import json
import os.path
import re
import traceback
from urllib.request import Request
from urllib.response import addinfourl
import urllib.error
import queue
import urllib.parse
import socket
import logging
import threading
from pathlib import Path
from typing import List, Tuple, Callable
from queue import Queue, Empty
import time

from chui_http import Context, HttpRequest, HttpResponse


# """配置日志记录器"""
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
# 后续直接使用即可
logger = logging.getLogger('Response_body_filter')


"""
# 必须实现以下方法
"""
def description() -> dict:
    """
    定义
    :return:
    typ: `1`为任务方式: 此时,`start`, `stop`方法生效
    request: 是否处理request数据
    response: 是否处理response数据
    layout: 列表定义，对应界面的列表
    """
    return {
        "typ": 0,
        "request": False,
        "response": True,
        "layout": {
            "headers": [
                {
                    "name": "关键信息",
                    "index": 1,
                },
                {
                    "name": "类型",
                    "index": 2,
                },
                {
                    "name": "公司",
                    "index": 3,
                }
            ]
        }
    }


OnDataHandler: Callable[[list], None]

def initialize(on_data_handler: Callable[[list], None]):
    global OnDataHandler
    OnDataHandler = on_data_handler
    load_extract_string()

    pass

def start() -> bool:
    """
    启动
    :return:
    """
    return True

def stop() -> bool:
    """
    停止
    :return:
    """
    return True

def on_request(context: Context, request: HttpRequest):
    """
    接收request数据
    :param context:
    :param request:
    :return:
    """
    return None

def on_response(context: Context, response: HttpResponse):
    """
    接收response数据
    :param context:
    :param response:
    :return:
    """
    global OnDataHandler

    if context.url.endswith(".js") is True:
        if response.body.isText and response.body.payload and isinstance(response.body.payload, str):
            result = extract_kv_with_regex(response.body.payload)
            data = []
            for row in result:
                reg_item = CUSTOM_REGEXS[row[0].lower()]
                data.append({
                    "data": [row[0], row[1], reg_item["title"], reg_item["company"], reg_item["homepage"], reg_item["address"]],
                    "context": {
                        "id": context.id
                    },
                })

            return data
        else:
            logger.warning(f"Invalid body:{context.id},{response.body}")


    return None

CUSTOM_REGEXS = dict()

def load_extract_string():
    global CUSTOM_REGEXS

    try:
        current_dir = Path(__file__).resolve().parent
        dict_file = os.path.join(current_dir, "extract-string-list.json")

        with open(dict_file, 'r', encoding='utf8') as file:
            tmp_kvs = json.load(file)
            for k, v in tmp_kvs.items():
                if 'disabled' in v and v['disabled'] == 1:
                    continue

                if 'reg' in v:
                    v['reg'] = re.compile(v['reg'])
                    CUSTOM_REGEXS[k] = v

                pass
            pass
        pass
    except Exception as exp:
        logger.error(f"Load Custom Regex Failed: {str(exp)}")

    pass

def extract_kv_with_regex(data):
    global CUSTOM_REGEXS

    custom_kvs = set()

    for key, regex_item in CUSTOM_REGEXS.items():
        for found in regex_item['reg'].findall(data):
            kv = (key, found)
            custom_kvs.add(kv)
        pass

    return custom_kvs


if __name__ == "__main__":
    def _on_data_hander(data):
        print(f"result:{data}")

    initialize(_on_data_hander)

    json_str = '{"context":{"id":"1","url":"http://127.0.0.1:8989/assets/js/main.js","scheme":"http","host":"192.168.100.133","port":8081,"cid":37,"ctime":1686556321938,"sid":5,"stime":1686556322722,"shared":null},"response":{"code":"200","message":"ok","protocol":"HTTP/1.1","headers":["Host: test.com","Sec-Fetch-Site: same-origin","Accept-Encoding: gzip, deflate, br","Connection: keep-alive","Sec-Fetch-Mode: cors","Accept: */*","User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15","Referer: https://test.com/","Sec-Fetch-Dest: empty","Accept-Language: zh-CN,zh-Hans;q=0.9"],"body":{"type":1,"payload":"dadasdadasdadasdadasdas,\\"AKIDaaaaaaaaaaaaa\\",dasdasdasdasdasdasd"}}}'
    data = json.loads(json_str)
    context = Context(data['context'])
    on_response(context, HttpResponse(data['response']))

    pass
