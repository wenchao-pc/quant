"""
飞书消息推送模块
"""
import os
import json
import requests


def get_feishu_webhook_url():
    """获取飞书webhook URL（从环境变量或配置文件）"""
    url = os.environ.get('FEISHU_WEBHOOK_URL', '')
    if url:
        return url
    
    # 尝试从配置文件读取
    config_path = os.path.expanduser('~/.hermes/quant/config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
            return config.get('feishu_webhook_url', '')
    
    return ''


def send_feishu_message(title, content, webhook_url=None):
    """发送飞书机器人消息"""
    if not webhook_url:
        webhook_url = get_feishu_webhook_url()
    
    if not webhook_url:
        print("⚠️ 未配置飞书Webhook，跳过推送")
        return False
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                }
            ]
        }
    }
    
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        result = r.json()
        if result.get('code') == 0 or result.get('StatusCode') == 0:
            print("✅ 飞书推送成功")
            return True
        else:
            print(f"❌ 飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 飞书推送异常: {e}")
        return False


def send_stock_report(results, webhook_url=None):
    """发送选股报告到飞书"""
    from main import format_report
    
    report = format_report(results, top=10)
    
    title = f"📈 A股量化选股 | {results[0]['name'] if results else '无信号'}领衔"
    
    # 转成飞书markdown格式
    md_content = report.replace('=', '—')
    
    return send_feishu_message(title, md_content, webhook_url)


if __name__ == '__main__':
    # 测试
    print("飞书推送模块就绪")
    print("使用方式: 设置环境变量 FEISHU_WEBHOOK_URL 或配置 ~/.hermes/quant/config.json")
