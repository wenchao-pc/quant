"""
量化选股报告生成器 - 双输出模式
1. JSON数据（给前端动态渲染）
2. 3套静态HTML（SEO友好 + 本地直接打开）
"""
import sys
import os
import json
import time
from datetime import datetime

# 路径设置
# report-generator/ 在 quant/ 下，quant-report/ 也在 quant/ 下
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ~/.hermes/quant/
QUANT_DIR = BASE_DIR        # quant系统根目录（import main.py等）
REPORT_DIR = os.path.join(BASE_DIR, 'quant-report')  # 前端仓库目录
sys.path.insert(0, QUANT_DIR)

from main import run_daily_screening, analyze_stock
from data.fetcher import get_top_volume_stocks, get_all_stocks


def get_report_date():
    """获取报告应使用的日期。
    - 今天是交易日且已收盘(15:05+) → 用今天
    - 今天是交易日但未收盘 → 用上一交易日
    - 今天非交易日 → 用最近的过去交易日
    """
    import akshare as ak
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    df = ak.tool_trade_date_hist_sina()
    trading_days = df["trade_date"].astype(str).tolist()
    
    # 今天是交易日且已过15:05 → 用今天
    if today_str in trading_days and (now.hour > 15 or (now.hour == 15 and now.minute >= 5)):
        return today_str
    
    # 未收盘或非交易日 → 找最近的过去交易日
    # 如果今天是交易日但未开盘，应该用上一个交易日
    past_days = [d for d in trading_days if d < today_str]
    if today_str in trading_days and now.hour < 15:
        # 今天是交易日但还没收盘，用上一个
        pass
    
    if past_days:
        last_trading_day = past_days[-1]
        if last_trading_day != today_str:
            print(f"⏭️ {today_str} 未收盘/非交易日，使用上一交易日 {last_trading_day}")
        return last_trading_day
    
    return today_str


def is_trading_day():
    """判断今天是否为A股交易日"""
    # 周末直接返回False
    weekday = datetime.now().weekday()
    if weekday >= 5:
        print("⏭️ 周末休市，跳过")
        return False
    # 用AKShare获取交易日历
    try:
        import akshare as ak
        today = datetime.now().strftime("%Y-%m-%d")
        df = ak.tool_trade_date_hist_sina()
        trading_days = df["trade_date"].astype(str).tolist()
        if today not in trading_days:
            print(f"⏭️ {datetime.now().strftime('%Y-%m-%d')} 非交易日，跳过")
            return False
        return True
    except Exception as e:
        print(f"⚠️ 交易日判断异常: {e}，默认继续运行")
        return True


def run_and_collect(top_n=80):
    """跑选股并收集所有数据"""
    report_date = get_report_date()
    now = datetime.now()
    # 如果报告日期不是今天（未收盘或非交易日），检查该日期报告是否已存在
    if report_date != now.strftime('%Y-%m-%d'):
        existing = os.path.join(REPORT_DIR, 'reports', report_date, 'data.json')
        if os.path.exists(existing):
            print(f"⏭️ {report_date} 报告已存在，跳过重复生成")
            return None
    
    # 清K线缓存，确保用最新数据
    import glob
    cache_files = glob.glob(os.path.join(QUANT_DIR, 'cache', 'hist_*.csv'))
    for f in cache_files:
        os.remove(f)
    if cache_files:
        print(f"  🗑️  清缓存: {len(cache_files)}个K线文件")
    
    print("📊 运行选股分析...")
    results = run_daily_screening(top_n=top_n)
    
    # 获取Top10（包括<70分的）
    import pandas as pd
    all_stocks_df = get_top_volume_stocks(10)
    top10 = []
    for idx, row in all_stocks_df.iterrows():
        code = str(row['代码']).zfill(6)
        name = row['名称']
        price = float(row['最新价']) if pd.notna(row['最新价']) else 0
        change_pct = float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0
        turnover = float(row['成交额']) if pd.notna(row['成交额']) else 0
        
        # 从results中找，没有就分析一次
        found = next((r for r in results if r['code'] == code), None)
        if found:
            top10.append(found)
        else:
            try:
                r = analyze_stock(code, name, price, change_pct, turnover)
                if r:
                    top10.append(r)
                else:
                    top10.append({
                        'name': name, 'code': code, 'total_score': 0,
                        'price': price, 'change_pct': change_pct, 'turnover': turnover,
                        'scores': {}, 'details': {}
                    })
            except:
                top10.append({
                    'name': name, 'code': code, 'total_score': 0,
                    'price': price, 'change_pct': change_pct, 'turnover': turnover,
                    'scores': {}, 'details': {}
                })
    
    # 获取大盘数据
    market = get_market_data()
    
    # 用 report_date（未收盘/非交易日时自动回退到上一交易日）
    from datetime import datetime as _dt
    report_dt = _dt.strptime(report_date, '%Y-%m-%d')
    data = {
        'date': report_date,
        'weekday': ['周一','周二','周三','周四','周五','周六','周日'][report_dt.weekday()],
        'generated_at': _dt.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_scanned': len(get_all_stocks()),
        'active_analyzed': top_n,
        'signal_count': len(results),
        'market': market,
        'signals': results,
        'top10': top10[:10],
        'backtest': {
            'win_rate': 63.6, 'avg_return': 2.66, 'sharpe': 2.36,
            'max_drawdown': -2.72, 'profit_factor': 2.46, 'annualized': 48.6,
            'total_trades': 50, 'signal_count': 11, 'period': '2026.1.9-4.17'
        }
    }
    
    return data


def get_market_data():
    """获取大盘指数数据"""
    import requests
    market = {}
    indices = {
        'sh000001': '上证指数',
        'sz399001': '深证成指', 
        'sz399006': '创业板指'
    }
    try:
        codes = ','.join(indices.keys())
        resp = requests.get(f'https://qt.gtimg.cn/q={codes}', timeout=10)
        resp.encoding = 'gbk'
        for line in resp.text.strip().split(';'):
            line = line.strip()
            if not line or '~' not in line:
                continue
            parts = line.split('~')
            if len(parts) > 5:
                code = parts[2] if len(parts) > 2 else ''
                market[code] = {
                    'name': parts[1],
                    'price': float(parts[3]) if parts[3] else 0,
                    'change_pct': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
                    'change': float(parts[31]) if len(parts) > 31 and parts[31] else 0,
                    'volume': float(parts[37]) if len(parts) > 37 and parts[37] else 0  # 成交额亿
                }
    except Exception as e:
        print(f"⚠️ 大盘数据获取失败: {e}")
        # 默认值
        market = {
            '000001': {'name':'上证指数','price':0,'change_pct':0,'change':0,'volume':0},
            '399001': {'name':'深证成指','price':0,'change_pct':0,'change':0,'volume':0},
            '399006': {'name':'创业板指','price':0,'change_pct':0,'change':0,'volume':0},
        }
    return market


def save_json(data):
    """保存JSON数据到日期文件夹内"""
    date_str = data['date']
    
    # 保存到 quant-report/reports/2026-04-18/data.json
    date_dir = os.path.join(REPORT_DIR, 'reports', date_str)
    os.makedirs(date_dir, exist_ok=True)
    json_path = os.path.join(date_dir, 'data.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON: {json_path}")
    
    # 同时保存到quant目录（兼容旧cron）
    compat_path = os.path.join(QUANT_DIR, 'quant_data.json')
    with open(compat_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return json_path


def get_trading_days_count(entry_date_str, today_str):
    """计算两个日期之间有多少个交易日后（不含入场日，含今天）"""
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        trading_days = df["trade_date"].astype(str).tolist()
        # 交易日历中找入场日和今天的索引
        if entry_date_str not in trading_days or today_str not in trading_days:
            return 0
        entry_idx = trading_days.index(entry_date_str)
        today_idx = trading_days.index(today_str)
        # 持仓天数 = 今天索引 - 入场日索引（含入场日当天）
        count = today_idx - entry_idx
        return max(0, count)
    except Exception:
        return 0

def update_trading(data):
    """更新信号追踪"""
    tracking_path = os.path.join(REPORT_DIR, 'data', 'tracking.json')
    
    # 加载已有追踪
    if os.path.exists(tracking_path):
        with open(tracking_path) as f:
            tracking = json.load(f)
    else:
        tracking = {'active': [], 'closed': [], 'summary': {'total_signals': 0, 'wins': 0, 'total_return': 0}}
    
    date_str = data['date']
    
    # 兼容老数据：自动补全 signal_history
    for pos in tracking['active'] + tracking['closed']:
        if 'signal_history' not in pos:
            pos['signal_history'] = [{
                'date': pos['entry_date'],
                'score': pos.get('entry_score', 0),
                'price': pos.get('entry_price', 0),
                'action': '首次入场'
            }]
    
    # 添加新信号到active
    today_codes = {sig['code'] for sig in data['signals']}
    for sig in data['signals']:
        # 检查是否已在active持仓中
        existing = next((a for a in tracking['active'] if a['code'] == sig['code']), None)
        if existing:
            # 持仓期间再次触发信号：重置计时器 + 更新分数 + 记录历史
            old_date = existing['entry_date']
            old_score = existing['entry_score']
            # 初始化信号历史
            if 'signal_history' not in existing:
                existing['signal_history'] = [{
                    'date': existing['entry_date'],
                    'score': existing['entry_score'],
                    'price': existing['entry_price'],
                    'action': '首次入场'
                }]
            # 追加本次触发记录
            existing['signal_history'].append({
                'date': date_str,
                'score': sig['total_score'],
                'price': sig['price'],
                'action': '信号增强-重置计时'
            })
            # 重置入场日期（重新开始算3天）
            existing['entry_date'] = date_str
            existing['entry_score'] = sig['total_score']
            existing['days'] = 0
            tracking['summary']['total_signals'] += 1
            print(f"🔄 {sig['name']}({sig['code']}) 信号增强: {old_score}→{sig['total_score']}分, 计时重置 ({old_date}→{date_str})")
            continue
        # 全新信号，加入持仓
        exists = any(a['code'] == sig['code'] and a['entry_date'] == date_str for a in tracking['active'])
        if not exists:
            tracking['active'].append({
                'name': sig['name'],
                'code': sig['code'],
                'entry_date': date_str,
                'entry_price': sig['price'],
                'entry_score': sig['total_score'],
                'current_price': sig['price'],
                'current_return': 0,
                'status': 'holding',
                'days': 0,
                'signal_history': [{
                    'date': date_str,
                    'score': sig['total_score'],
                    'price': sig['price'],
                    'action': '首次入场'
                }]
            })
            tracking['summary']['total_signals'] += 1
    
    # 注意：不移除旧持仓！持仓股票在持有期间分数会波动回落，不再触发信号是正常的
    # 只有超时平仓逻辑（下面）才会移出追踪
    
    # 更新active持仓的当前价格和收益
    # （简化版：用当日数据，实际应该获取最新价）
    # 更新持仓实时行情
    import requests
    try:
        codes_str = ','.join([f'sh{p["code"]}' if p['code'].startswith(('6', '5')) else f'sz{p["code"]}' for p in tracking['active']])
        resp = requests.get(f'https://qt.gtimg.cn/q={codes_str}', timeout=8)
        resp.encoding = 'gbk'
        price_map = {}
        for line in resp.text.strip().split(';'):
            if '~' not in line:
                continue
            parts = line.strip().split('~')
            if len(parts) < 5:
                continue
            code_raw = parts[0].replace('v_', '').split('="')[0]  # e.g. 'sz000651'
            for prefix in ('sh', 'sz'):
                if code_raw.startswith(prefix):
                    code_full = code_raw[len(prefix):]
                    break
            else:
                continue
            try:
                current_price = float(parts[3])
            except:
                current_price = 0
            price_map[code_full] = current_price

        for pos in tracking['active']:
            code = pos['code']
            entry_price = pos.get('entry_price', 0)
            current_price = price_map.get(code, entry_price)
            pos['current_price'] = current_price
            if entry_price > 0:
                pos['current_return'] = round((current_price - entry_price) / entry_price * 100, 2)
            else:
                pos['current_return'] = 0
    except Exception as e:
        print(f"⚠️ 实时行情更新失败: {e}")

    # 自动平仓：超过3天或达到止盈止损
    still_active = []
    for pos in tracking['active']:
        if pos['entry_date'] == date_str:
            still_active.append(pos)
            continue
        # 计算交易日天数（用交易日历，排除节假日和周末）
        days = get_trading_days_count(pos['entry_date'], date_str)
        
        if days >= 3:
            # 超时平仓
            pos['status'] = 'timeout'
            pos['exit_date'] = date_str
            pos['exit_reason'] = f'持有{days}天，自动平仓'
            tracking['closed'].append(pos)
            tracking['summary']['total_return'] += pos.get('current_return', 0)
            if pos.get('current_return', 0) > 0:
                tracking['summary']['wins'] += 1
        else:
            pos['days'] = days
            still_active.append(pos)
    
    tracking['active'] = still_active
    
    # 按买入日期降序排序，最新的在前面
    tracking['active'].sort(key=lambda x: x['entry_date'], reverse=True)
    
    with open(tracking_path, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, ensure_ascii=False, indent=2)
    print(f"✅ Tracking: {tracking_path}")
    
    return tracking_path


def get_all_reports():
    """获取所有已有报告列表"""
    reports_dir = os.path.join(REPORT_DIR, 'reports')
    reports = []
    if os.path.exists(reports_dir):
        for name in sorted(os.listdir(reports_dir), reverse=True):
            dir_path = os.path.join(reports_dir, name)
            if not os.path.isdir(dir_path):
                continue
            json_path = os.path.join(dir_path, 'data.json')
            if not os.path.exists(json_path):
                continue
            with open(json_path, encoding='utf-8') as fp:
                d = json.load(fp)
            reports.append({
                'date': d['date'],
                'weekday': d.get('weekday', ''),
                'signal_count': d.get('signal_count', 0),
                'total_scanned': d.get('total_scanned', 0),
            })
    return reports


def generate_all(data):
    """生成全部输出：JSON + 3个静态HTML"""
    date_str = data['date']
    
    # 1. 保存JSON
    json_path = save_json(data)
    
    # 2. 生成3套静态HTML
    from templates.broker import render_broker
    from templates.social import render_social
    from templates.hacker import render_hacker
    
    date_dir = os.path.join(REPORT_DIR, 'reports', date_str)
    os.makedirs(date_dir, exist_ok=True)
    
    broker_html = render_broker(data)
    broker_path = os.path.join(date_dir, 'broker.html')
    with open(broker_path, 'w', encoding='utf-8') as f:
        f.write(broker_html)
    print(f"✅ 券商晨报: {broker_path}")
    
    social_html = render_social(data)
    social_path = os.path.join(date_dir, 'social.html')
    with open(social_path, 'w', encoding='utf-8') as f:
        f.write(social_html)
    print(f"✅ 社交卡片: {social_path}")
    
    hacker_html = render_hacker(data)
    hacker_path = os.path.join(date_dir, 'hacker.html')
    with open(hacker_path, 'w', encoding='utf-8') as f:
        f.write(hacker_html)
    print(f"✅ 黑客终端: {hacker_path}")
    
    # 3. 更新追踪
    tracking_path = update_trading(data)
    
    # 4. 更新主页的report-list.json
    report_list = get_all_reports()
    list_path = os.path.join(REPORT_DIR, 'data', 'report-list.json')
    with open(list_path, 'w', encoding='utf-8') as f:
        json.dump(report_list, f, ensure_ascii=False, indent=2)
    print(f"✅ 报告列表: {list_path}")
    
    return {
        'json': json_path,
        'broker': broker_path,
        'social': social_path,
        'hacker': hacker_path,
        'tracking': tracking_path,
        'report_list': list_path,
    }


if __name__ == '__main__':
    data = run_and_collect()
    if data is None:
        print("今日非交易日，退出")
    else:
        paths = generate_all(data)
        print(f"\n🌐 主页: file://{os.path.join(REPORT_DIR, 'index.html')}")
        print(f"📄 社交风格: file://{paths['social']}")
