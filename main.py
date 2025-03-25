import configparser
import json
import requests
import base64
from urllib.parse import quote
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import sys

# 初始化日志配置
logging.basicConfig(
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

class ConfigManager:
    """配置管理器：环境变量 > 配置文件 > 默认值"""
    def __init__(self):
        # 动态获取配置文件路径（支持通过环境变量覆盖）
        config_file = os.getenv("CONFIG_FILE", "conf.env")
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')

    def get(self, key, default=None, required=False):
        """获取配置项：环境变量 > 配置文件 > 默认值"""
        value = os.getenv(key)
        if value is not None:
            return value.strip()

        config_value = self.config['DEFAULT'].get(key)
        if config_value:
            return config_value.strip()

        if default is not None:
            return default

        if required:
            logging.error(f"必须设置 {key} 配置项")
            sys.exit(1)

        return None

def load_config():
    config_mgr = ConfigManager()
    base_url = config_mgr.get("BASE_URL", required=True)

    def get_url_list(key):
        raw = config_mgr.get(key, "")
        return [url.strip() for url in raw.split(',') if url.strip()]

    return {
        "BASE_URL": base_url,
        "SUB_URLS": get_url_list("SUB_URLS"),
        "UP_URLS": get_url_list("UP_URLS"),
        "RE_URLS": get_url_list("RE_URLS")
    }

CONFIG = load_config()

def read_file_from_url(url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        logging.info(f"INFO: Response from {url}: {response.status_code} {response.headers}")
        return response.content
    except requests.exceptions.RequestException as e:
        logging.error(f"ERROR: 读取 {url} 时发生错误: {e}")
        return None

def merge_files_from_urls(url_list):
    merged_content = b""
    for url in url_list:
        content = read_file_from_url(url)
        if content is not None:
            merged_content += content
        else:
            logging.warning(f"WARNING: 无法读取文件 {url}，跳过")
    return merged_content

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Hello, World!")
        elif self.path == '/sub':
            self.handle_sub()
        elif self.path == '/up':
            self.handle_up()
        elif self.path == '/re':
            self.handle_re()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        self.do_GET()

    def handle_sub(self):
        urls = CONFIG["SUB_URLS"]
        full_urls = [CONFIG["BASE_URL"] + quote(url, safe=':/?&=') for url in urls]
        merged_content = merge_files_from_urls(full_urls)

        if merged_content:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(base64.b64encode(merged_content))
        else:
            self.send_error(500, "无法合并文件")

    def handle_up(self):
        urls = CONFIG["UP_URLS"]
        merged_content = merge_files_from_urls(urls)

        if merged_content:
            try:
                content_str = merged_content.decode('utf-8')
                response = {"status": 200, "content": content_str}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except UnicodeDecodeError:
                self.send_error_with_json(400, "内容无法解码为文本")
        else:
            self.send_error_with_json(500, "无法请求up")

    def handle_re(self):
        urls = CONFIG["RE_URLS"]
        merged_content = merge_files_from_urls(urls)

        if merged_content:
            try:
                content_str = merged_content.decode('utf-8')
                response = {"status": 200, "content": content_str}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except UnicodeDecodeError:
                self.send_error_with_json(400, "内容无法解码为文本")
        else:
            self.send_error_with_json(500, "无法请求re")

    def send_error_with_json(self, code, message):
        """统一错误响应格式"""
        response = {
            "status": code,
            "error": message
        }
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

if __name__ == '__main__':
    server_address = ('0.0.0.0', 8080)
    httpd = HTTPServer(server_address, handler)
    logging.info(f"服务器运行在 http://0.0.0.0:{server_address[1]}")
    httpd.serve_forever()
