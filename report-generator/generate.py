"""
量化选股报告生成器 - 双输出模式
1. JSON数据（给前端动态渲染）
2. 3套静态HTML（SEO友好 + 本地直接打开）
"""
import sys
import os
import json
import time
import tempfile
from datetime import datetime

# 自动加载 .env 环境变量
_dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(_dotenv_path):
    with open(_dotenv_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())


def atomic_json_write(obj, path):
    """原子写入JSON：先写临时文件再rename，防止进程崩溃损坏数据"""
    dir_path = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

# 路径设置
# report-generator/ 在 quant/ 下，quant-report/ 也在 quant/ 下
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ~/.hermes/quant/
QUANT_DIR = BASE_DIR        # quant系统根目录（import main.py等）
REPORT_DIR = os.path.join(BASE_DIR, 'quant-report')  # 前端仓库目录
sys.path.insert(0, QUANT_DIR)

from main import run_daily_screening, analyze_stock
from data.fetcher import get_top_volume_stocks, get_all_stocks


def is_trading_day():
    """判断今天是否为A股交易日"""
    # 周末直接返回False
    weekday = datetime.now().weekday()
    if weekday >= 5:
        print("⏭️ 周末休市，跳过")
        return False
    # 用baostock获取交易日历
    try:
        import baostock as bs
        lg = bs.login()
        today = datetime.now().strftime("%Y-%m-%d")
        rs = bs.query_trade_dates(start_date=today, end_date=today)
        is_trading = False
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            if row[1] == '1':
                is_trading = True
        if not is_trading:
            print(f"⏭️ {today} 非交易日，跳过")
            return False
        return True
    except Exception as e:
        print(f"⚠️ 交易日判断异常: {e}，默认继续运行")
        return True
    finally:
        try:
            bs.logout()
        except Exception:
            pass


def _should_use_today(now):
    """判断是否生成今日报告：
    - 交易日 + 盘后(>=15:05) → True
    - 非交易日或盘中 → False（生成上一交易日）
    """
    today = now.strftime('%Y-%m-%d')

    # 周末 → 非交易日
    if now.weekday() >= 5:
        return False

    bs = None
    # 用baostock确认是否交易日
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_trade_dates(start_date=today, end_date=today)
        is_trading = False
        while (rs.error_code == '0') and rs.next():
            if rs.get_row_data()[1] == '1':
                is_trading = True
        if not is_trading:
            return False
    except Exception:
        return False
    finally:
        if bs is not None:
            try:
                bs.logout()
            except Exception:
                pass

    # 交易日：盘后(>=15:05) → 今日；盘中 → 上一交易日
    return (now.hour + now.minute / 60.0) >= 15.05


def _get_previous_trading_date(today):
    """获取上一个交易日（不含today），用baostock"""
    bs = None
    try:
        import baostock as bs
        from datetime import timedelta
        bs.login()
        start = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
        rs = bs.query_trade_dates(start_date=start, end_date=today)
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        for row in reversed(rows):
            if row[0] < today and row[1] == '1':
                return row[0]
    except Exception:
        pass
    finally:
        if bs is not None:
            try:
                bs.logout()
            except Exception:
                pass
    # 降级：往前推1-2天（跳过周末）
    from datetime import timedelta
    d = datetime.strptime(today, '%Y-%m-%d')
    for i in range(1, 8):
        prev = (d - timedelta(days=i)).strftime('%Y-%m-%d')
        wd = datetime.strptime(prev, '%Y-%m-%d').weekday()
        if wd < 5:
            return prev
    return today


def get_backtest_stats():
    """从 tracking.json 动态计算策略战绩"""
    import math
    tracking_path = os.path.join(REPORT_DIR, 'data', 'tracking.json')
    if not os.path.exists(tracking_path):
        return {'win_rate': 0, 'avg_return': 0, 'sharpe': 0, 'max_drawdown': 0, 'profit_factor': 0, 'total_trades': 0, 'signal_count': 0, 'period': '暂无数据'}
    with open(tracking_path) as f:
        tracking = json.load(f)
    
    closed = tracking.get('closed', [])
    total_trades = len(closed)
    if total_trades == 0:
        return {'win_rate': 0, 'avg_return': 0, 'sharpe': 0, 'max_drawdown': 0, 'profit_factor': 0, 'total_trades': 0, 'signal_count': 0, 'period': '暂无数据'}
    
    returns = [p.get('current_return', 0) for p in closed]
    wins = sum(1 for r in returns if r > 0)
    total_return = round(sum(returns), 2)
    win_rate = round(wins / total_trades * 100, 1)
    avg_return = round(total_return / total_trades, 2)
    max_drawdown = round(min(returns), 2)
    max_return = round(max(returns), 2)
    
    gains = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    profit_factor = round(abs(sum(gains) / (sum(losses) + 0.01)), 2) if losses else 0
    
    std = math.sqrt(sum((r - avg_return)**2 for r in returns) / total_trades) if total_trades > 1 else 0.5
    sharpe = round(avg_return / (std + 0.1), 2)
    
    entry_dates = [p['entry_date'] for p in closed if p.get('entry_date')]
    period = f"{min(entry_dates)}至{max(entry_dates)}" if entry_dates else '暂无'
    
    return {
        'win_rate': win_rate,
        'avg_return': avg_return,
        'avg_return_str': f"+{avg_return}" if avg_return > 0 else str(avg_return),
        'sharpe': sharpe,
        'max_drawdown': max_drawdown,
        'profit_factor': profit_factor,
        'annualized': round(avg_return * 50, 1),  # 估算年化（每年约50个交易日）
        'max_return': max_return,
        'total_trades': total_trades,
        'signal_count': tracking.get('summary', {}).get('total_signals', total_trades),
        'total_return': total_return,
        'period': period
    }


def run_and_collect(top_n=40, date_str=None):
    """跑选股并收集所有数据。

    报告日期判断逻辑（date_str 为 None 时生效）：
    - 交易日 + 盘后(>=15:05) → 生成今日报告
    - 盘中(<15:05) 或 非交易日 → 生成上一交易日报告（历史模式）

    date_str 不为 None 时：直接用指定日期运行（历史模式）
    """
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')

    # 有date_str → 强制历史模式
    if date_str is not None:
        is_historical = True
        print(f"📅 历史报告模式: {date_str}")
    else:
        # 无date_str → 按报告日期判断逻辑决定
        is_historical = not _should_use_today(now)

    if is_historical:
        if date_str is None:
            date_str = _get_previous_trading_date(today_str)
            print(f"  📅 今日({today_str}盘中/非交易日)，生成上一交易日({date_str})报告")
        # 清K线缓存（历史模式用收盘数据）
        import glob
        cache_files = glob.glob(os.path.join(QUANT_DIR, 'cache', 'hist_*.csv'))
        for f in cache_files:
            os.remove(f)
        if cache_files:
            print(f"  🗑️  清缓存: {len(cache_files)}个K线文件")
    else:
        # 今日报告模式
        date_str = today_str
        print(f"  📅 今日({today_str}盘后)，生成今日报告")
        # 清K线缓存（今日实时模式也清）
        import glob
        cache_files = glob.glob(os.path.join(QUANT_DIR, 'cache', 'hist_*.csv'))
        for f in cache_files:
            os.remove(f)
        if cache_files:
            print(f"  🗑️  清缓存: {len(cache_files)}个K线文件")

    print("📊 运行选股分析...")
    results = run_daily_screening(top_n=top_n, date_str=date_str)
    
    # 获取Top10（包括<70分的）
    import pandas as pd
    all_stocks_df = get_top_volume_stocks(10, date_str=date_str)
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
                r = analyze_stock(code, name, price, change_pct, turnover, date_str=date_str)
                if r:
                    top10.append(r)
                else:
                    top10.append({
                        'name': name, 'code': code, 'total_score': 0,
                        'price': price, 'change_pct': change_pct, 'turnover': turnover,
                        'scores': {}, 'details': {}
                    })
            except Exception as exc:
                top10.append({
                    'name': name, 'code': code, 'total_score': 0,
                    'price': price, 'change_pct': change_pct, 'turnover': turnover,
                    'scores': {}, 'details': {}
                })
    
    # 获取大盘数据
    market = get_market_data()
    
    # 从 tracking.json 动态计算策略战绩
    backtest = get_backtest_stats()
    
    data = {
        'date': date_str,
        'weekday': ['周一','周二','周三','周四','周五','周六','周日'][datetime.strptime(date_str, '%Y-%m-%d').weekday()],
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_scanned': len(get_all_stocks(date_str=date_str)),
        'active_analyzed': top_n,
        'threshold': 70,
        'signal_count': len(results),
        'market': market,
        'signals': results,
        'top10': top10[:10],
        'backtest': backtest
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
    atomic_json_write(data, json_path)
    print(f"✅ JSON: {json_path}")

    # 同时保存到quant目录（兼容旧cron）
    compat_path = os.path.join(QUANT_DIR, 'quant_data.json')
    with open(compat_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return json_path


def get_trading_days_count(entry_date_str, today_str):
    """计算两个日期之间有多少个交易日后（不含入场日，含今天）"""
    bs = None
    try:
        import baostock as bs
        lg = bs.login()
        rs = bs.query_trade_dates(start_date=entry_date_str, end_date=today_str)
        count = 0
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            if row[1] == '1' and row[0] != entry_date_str:
                count += 1
        return max(0, count)
    except Exception:
        return 0
    finally:
        if bs is not None:
            try:
                bs.logout()
            except Exception:
                pass

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
    
    # 对比 data.signals，清理不再属于信号的 active 持仓（脏数据清理）
    signal_codes = {sig['code'] for sig in data['signals']}
    stale_active = []
    for pos in tracking['active']:
        if pos['code'] not in signal_codes:
            # 信号消失，清理出场
            pos['status'] = 'signal_lost'
            pos['exit_date'] = date_str
            pos['exit_reason'] = '信号消失，清理出场'
            tracking['closed'].append(pos)
            print(f"🧹 清理脏数据: {pos['name']}({pos['code']}) 不在最新signals中，标记平仓")
        else:
            stale_active.append(pos)
    tracking['active'] = stale_active
    
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
            except (ValueError, IndexError):
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
    
    atomic_json_write(tracking, tracking_path)
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
                'generated_at': d.get('generated_at', ''),
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
    atomic_json_write(report_list, list_path)
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
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    data = run_and_collect(date_str=date_str)
    paths = generate_all(data)
    print(f"\n🌐 主页: file://{os.path.join(REPORT_DIR, 'index.html')}")
    print(f"📄 社交风格: file://{paths['social']}")
