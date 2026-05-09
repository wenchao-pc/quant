"""
量化报告本地HTTP服务
解决file://协议下JS无法加载JSON的跨域问题
"""
import http.server
import socketserver
import os
import webbrowser
import argparse

# 前端仓库目录
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'quant-report')


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    """添加CORS头 + JSON正确MIME类型"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=REPORT_DIR, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    
    def guess_type(self, path):
        if path.endswith('.json'):
            return 'application/json; charset=utf-8'
        return super().guess_type(path)
    
    def log_message(self, format, *args):
        # 简化日志，只显示请求路径
        print(f"  {args[0]}")


def main():
    parser = argparse.ArgumentParser(description='量化报告HTTP服务')
    parser.add_argument('-p', '--port', type=int, default=8080, help='端口号 (默认8080)')
    parser.add_argument('-o', '--open', action='store_true', default=True, help='自动打开浏览器')
    parser.add_argument('--no-open', dest='open', action='store_false', help='不打开浏览器')
    args = parser.parse_args()
    
    port = args.port
    
    # 端口被占用时自动+1
    for attempt in range(5):
        try:
            handler = CORSHandler
            with socketserver.TCPServer(("", port), handler) as httpd:
                url = f"http://localhost:{port}"
                print(f"╔══════════════════════════════════════╗")
                print(f"║  📈 量化报告系统已启动              ║")
                print(f"║  🌐 {url:<33s}║")
                print(f"║  📂 {REPORT_DIR:<33s}║")
                print(f"║  ⏹️  Ctrl+C 停止                     ║")
                print(f"╚══════════════════════════════════════╝")
                
                if args.open:
                    webbrowser.open(url)
                
                httpd.serve_forever()
        except OSError:
            print(f"⚠️ 端口 {port} 被占用，尝试 {port+1}...")
            port += 1
        except KeyboardInterrupt:
            print("\n👋 服务已停止")
            break


if __name__ == '__main__':
    main()
