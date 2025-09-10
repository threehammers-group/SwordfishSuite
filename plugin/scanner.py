# -*- encoding: utf-8 -*-
import json
import os.path
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


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """自定义重定向处理器，禁止重定向"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # 返回 None 表示不处理重定向


# 创建自定义的 OpenerDirector，禁用重定向
opener = urllib.request.build_opener(NoRedirectHandler)
urllib.request.install_opener(opener)  # 全局生效（可选）


# """配置日志记录器"""
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
# 后续直接使用即可
logger = logging.getLogger('URLScanner')


# url编码
def _normalize_and_encode_url(url: str) -> str:
    """标准化并编码URL"""
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    url = url.rstrip('/')

    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")

        # 编码各组件
        encoded_path = urllib.parse.quote(parsed.path) if parsed.path else ""
        encoded_query = urllib.parse.quote(parsed.query) if parsed.query else ""
        encoded_fragment = urllib.parse.quote(parsed.fragment) if parsed.fragment else ""

        # 重建URL并确保格式正确
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),  # 域名小写化
            encoded_path,
            parsed.params,
            encoded_query,
            encoded_fragment
        ))

        return normalized
    except Exception as e:
        logger.error(f"[-]Parsed url failed: {e}")
        raise


# 获取response长度
def _get_response_length(response: addinfourl|None) -> int:
    if response is None:
        return 0

    content_length = response.getheader("Content-Length")
    if content_length:
        return int(content_length)
    else:
        data = response.read()
        response.close()
        return len(data)

# 扫描器
class Scanner:
    def __init__(self, target: str, unique_paths: set, new_data_handler: Callable[[list, Request, addinfourl], None] = None, thread_num: int = 10, timeout: int = 5):
        """
        初始化扫描器

        :param target: 目标URL（可包含非ASCII字符）
        :param unique_paths: 字典文件路径
        :param thread_num: 工作线程数
        :param timeout: 请求超时时间(秒)
        """
        self.target = _normalize_and_encode_url(target)
        self.new_data_handler = new_data_handler
        self.thread_num = min(max(thread_num, 1), 50)  # 限制线程数在1-50之间
        self.timeout = timeout

        # 存储扫描结果
        # self.results: []

        # 任务队列和线程控制
        self.paths = queue.Queue()
        for path in unique_paths:
            self.paths.put(path)
        self.total_paths = len(unique_paths)

        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._threads: List[threading.Thread] = []

        # 统计信息
        self.start_time = 0.0
        self.end_time = 0.0
        self.scanned_paths = 0
        self.successful_scans = 0
        self.failed_scans = 0

    def scan(self) -> bool:
        """启动扫描"""
        if self._running:
            logger.warning("[-]Scanner already running")
            return False

        with self._lock:
            self._running = True
            self._stop_event.clear()
            # self.results.clear()
            self.start_time = time.time()
            self.scanned_paths = 0
            self.successful_scans = 0
            self.failed_scans = 0

            # 创建工作线程
            for i in range(self.thread_num):
                t = threading.Thread(
                    target=self._worker,
                    name=f"ScannerWorker-{i}",
                    daemon=True
                )
                t.start()
                self._threads.append(t)

        logger.info(f"[+]Scanner Start[{self.target}], threads[{self.thread_num}]")
        return True

    def _make_request(self, url: str) -> Tuple[int, Request, addinfourl|None]:
        """执行HTTP请求并返回状态码和响应大小"""
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; URLScanner/1.0)',
                'Accept-Encoding': 'gzip, deflate'
            },
            method='GET'
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return 0, req, response
        except urllib.error.HTTPError as e:
            # HTTPError 本身就是响应对象，可以直接返回
            return e.code, req, e
        except (urllib.error.URLError, socket.timeout, socket.error) as e:
            logger.warning(f"[-]Request error: {url} - {str(e)}")
            return -1, req, None  # 使用-1表示网络错误
        except Exception as e:
            logger.warning(f"[-]Request unknown error: {url} - {str(e)}")
            return -2, req, None  # 使用-2表示其他错误

    def _worker(self):
        """工作线程执行函数"""
        while not self._stop_event.is_set() and self._running:
            try:
                path = self.paths.get_nowait()
                url = f"{self.target}/{path.lstrip('/')}"

                code, req, response = self._make_request(url)

                with self._lock:
                    if code >= 0:
                        if code == 0:
                            status = response.status
                        else:
                            status = code

                        if status in [200, 403] or (300 <= status < 400):  # 只记录成功的HTTP请求
                            self.new_data_handler([url, status], req, response)
                            self.successful_scans += 1
                        else:
                            self.failed_scans += 1
                    else:
                        self.failed_scans += 1

                    self.scanned_paths += 1

                    # 每扫描100个路径打印一次进度
                    if self.scanned_paths % 100 == 0:
                        self._print_progress()

                self.paths.task_done()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"[-]Worker thread error: {(e)}")
                traceback.print_exc()
            pass
        pass

    def _print_progress(self):
        """打印扫描进度"""
        if self.total_paths > 0:
            percent = (self.scanned_paths / self.total_paths) * 100
            logger.info(
                f"[{self.target}] "
                f"progress: {self.scanned_paths}/{self.total_paths} ({percent:.1f}%) "
                f"succeed: {self.successful_scans}, failed: {self.failed_scans}"
            )

    def wait_for_completion(self):
        self.paths.join()

        with self._lock:
            self._running = False
            self._stop_event.set()
            self.end_time = time.time()

        self._print_stats()
        logger.info(f"[+]Scanner is completed[{self.target}]")

    def cancel(self):
        """停止扫描"""
        if not self._running:
            return False

        with self._lock:
            self._running = False
            self._stop_event.set()
            self.end_time = time.time()

            # 清空队列以快速停止线程
            while not self.paths.empty():
                self.paths.get()
                self.paths.task_done()

        # 等待线程结束
        for t in self._threads:
            t.join(timeout=1)

        duration = self.end_time - self.start_time
        logger.info(f"[+]Scanner is stopped, took {duration:.2f}s")
        self._print_stats()
        return True

    def _print_stats(self):
        """打印统计信息"""
        with self._lock:
            duration = self.end_time - self.start_time
            req_per_sec = self.scanned_paths / duration if duration > 0 else 0

            logger.info(f"Scan stat[{self.target}]: "
                        f"paths: {self.total_paths}"
                        f", scanned: {self.scanned_paths} ({self.scanned_paths / self.total_paths * 100:.1f}%)"
                        f", rate: {req_per_sec:.2f}"
                        f", succeed: {self.successful_scans}"
                        f", failed: {self.failed_scans}")

            pass
        pass

    # def get_results(self) -> Dict[str, int]:
    #     """获取所有结果 (URL: (status_code, size))"""
    #     with self._lock:
    #         return self.results.copy()

    def is_running(self) -> bool:
        """检查是否正在运行"""
        with self._lock:
            return self._running

    def dispose(self):
        """释放资源"""
        self.cancel()
        with self._lock:
            # self.results.clear()
            self._threads.clear()

    pass


# 定义扫描管理器，存储扫描结果
class ScannerManager:
    def __init__(self, dict_file: str, max_concurrent: int = 10, on_data_handler: Callable[[list], None] = None):
        self.dict_file = dict_file
        # absolute_path = Path(dict_file).resolve()
        # print(f'absolute_path:{absolute_path}')

        self.unique_paths = set()
        self.max_concurrent = max_concurrent

        self._buffer_lock = threading.Lock()

        # 任务管理
        self.processed_targets = set()
        self.target_queue = Queue()
        self.running_scanners: List[Scanner] = []
        self.worker_threads: List[threading.Thread] = []
        self.is_running = False

        self.on_data_handler = on_data_handler
        pass

    def start(self) -> bool:
        """启动扫描服务"""
        if self.is_running:
            return False

        if self._load_dict() is False:
            return False

        self.is_running = True
        for _ in range(self.max_concurrent):
            thread = threading.Thread(target=self._worker)
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)

        logger.info(f"[+]Start scan manager")

        return True

    def stop(self) -> bool:
        """停止扫描服务"""
        if not self.is_running:
            return False

        with self._buffer_lock:
            self.is_running = False
            for scanner in self.running_scanners:
                scanner.cancel()
            self.running_scanners.clear()

        for thread in self.worker_threads:
            thread.join()
        self.worker_threads.clear()

        logger.info(f"[+]Stopped scan manager")

        return True

    def _load_dict(self) -> bool:
        """安全加载字典文件"""
        encodings = ['utf-8', 'gb18030', 'latin-1']

        for enc in encodings:
            try:
                with open(self.dict_file, 'r', encoding=enc) as f:
                    for line in f:
                        path = line.strip()
                        if path and not path.startswith(('#', ';', '//')):
                            try:
                                # 标准化路径
                                path = path.lstrip('/')
                                safe_path = urllib.parse.quote(path)
                                self.unique_paths.add(safe_path)
                            except Exception as e:
                                logger.warning(f"[-]Parsed url error: {path} - {e}")
                                continue

                total_paths = len(self.unique_paths)
                logger.info(f"[+]Load path from dicts [{total_paths}](encoding: {enc})")
                if total_paths > 0:
                    return True
                return False
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"[-]Load path from dicts error: {e}")
                raise e

        logger.error(f"[-]Load path from dicts failed")
        return False

    def add_target(self, context: Context, request: HttpRequest) -> bool:
        if context.port in [80, 443]:
            target = f'{context.scheme}://{context.host}'
        else:
            target = f'{context.scheme}://{context.host}:{context.port}'

        """添加扫描目标, 已添加过的目标会忽略"""
        if target in self.processed_targets:
            # logger.info(f"[+]Target already exists: [{target}]")
            return False

        self.processed_targets.add(target)
        self.target_queue.put(target)

        logger.info(f"[+]Add target: [{target}]")

        return True

    def _worker(self):
        """工作线程核心逻辑"""
        while self.is_running:
            try:
                target = self.target_queue.get(timeout=1)

                # 创建带回调的Scanner
                scanner = Scanner(
                    target=target,
                    unique_paths=self.unique_paths,
                    new_data_handler=self._handle_new_results  # 绑定回调
                )

                with self._buffer_lock:
                    self.running_scanners.append(scanner)

                scanner.scan()
                scanner.wait_for_completion()

                with self._buffer_lock:
                    if scanner in self.running_scanners:
                        self.running_scanners.remove(scanner)

                self.target_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                print(f"[-]Scan manager worker error: {str(e)}")

    def _handle_new_results(self, result: list, req: Request, response: addinfourl):
        httpRequest = HttpRequest.from_urllib_request(req)
        httpResp = HttpResponse.from_urllib_response(response)
        if httpResp.body.isText and httpResp.body.payload and isinstance(httpResp.body.payload, str):
            result.append(len(httpResp.body.payload))
        else:
            result.append(0)

        self.on_data_handler([
            {
                "data": result,
                "request": httpRequest.serialize(),
                "response": httpResp.serialize(),
            }
        ])

    pass


manager:ScannerManager = None

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
        "typ": 1,
        "request": True,
        "response": False,
        "layout": {
            "headers": [
                {
                    "name": "URL",
                    "index": 0,
                },
                {
                    "name": "状态码",
                    "index": 1,
                }
            ]
        }
    }

def initialize(on_data_handler: Callable[[list], None]):
    """
    初始化
    :param on_data_handler: 数据处理完成的回调函数
    内容为二位数组list[list]，索引位与description.layout.headers对应
    :return:
    """
    global manager

    current_dir = Path(__file__).resolve().parent
    dict_file = os.path.join(current_dir, "DIR.txt")

    manager = ScannerManager(
        dict_file=dict_file,
        max_concurrent=1,
        on_data_handler=on_data_handler
    )

def start() -> bool:
    """
    启动
    :return:
    """
    global manager
    return manager.start()

def stop() -> bool:
    """
    停止
    :return:
    """
    global manager
    return manager.stop()

def on_request(context: Context, request: HttpRequest):
    """
    接收request数据
    :param context:
    :param request:
    :return:
    """
    global manager
    manager.add_target(context, request)
    return None

def on_response(context: Context, response: HttpResponse):
    """
    接收response数据
    :param context:
    :param response:
    :return:
    """
    global manager
    return None


if __name__ == "__main__":
    print("?????????????????????????")
    def _worker(num):
        time.sleep(2)

        print("add1")
        json_str = '{"context":{"url":"https://test.com/assets/js/main.js","scheme":"https","host":"www.speedtest.cn","port":443,"cid":37,"ctime":1686556321938,"sid":5,"stime":1686556322722},"request":{"method":"GET","path":"/assets/js/main.js","protocol":"HTTP/1.1","headers":["Host: test.com","Sec-Fetch-Site: same-origin","Accept-Encoding: gzip, deflate, br","Connection: keep-alive","Sec-Fetch-Mode: cors","Accept: */*","User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15","Referer: https://test.com/","Sec-Fetch-Dest: empty","Accept-Language: zh-CN,zh-Hans;q=0.9"],"body":{"type":0,"payload":null}}}'
        data = json.loads(json_str)
        context = Context(data['context'])
        result = on_request(context, HttpRequest(data['request']))

        time.sleep(10)
        print("add2")

        json_str = '{"context":{"url":"http://127.0.0.1:8989/assets/js/main.js","scheme":"http","host":"192.168.100.133","port":8081,"cid":37,"ctime":1686556321938,"sid":5,"stime":1686556322722},"request":{"method":"GET","path":"/assets/js/main.js","protocol":"HTTP/1.1","headers":["Host: test.com","Sec-Fetch-Site: same-origin","Accept-Encoding: gzip, deflate, br","Connection: keep-alive","Sec-Fetch-Mode: cors","Accept: */*","User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15","Referer: https://test.com/","Sec-Fetch-Dest: empty","Accept-Language: zh-CN,zh-Hans;q=0.9"],"body":{"type":0,"payload":null}}}'
        data = json.loads(json_str)
        context = Context(data['context'])
        result = on_request(context, HttpRequest(data['request']))


    def _on_data_hander(data):
        print(f"result:{data}")

    initialize(_on_data_hander)
    start()

    # 创建线程, 添加数据
    t = threading.Thread(target=_worker, args=(1,))
    t.start()  # 启动线程

    while True:
        time.sleep(1)

    pass
