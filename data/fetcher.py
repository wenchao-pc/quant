"""
A股数据获取模块 - 腾讯行情API（稳定可靠）
"""
import requests
import pandas as pd
import numpy as np
import os
import time
import re
from datetime import datetime, timedelta


# ── 报告日期判断 ──────────────────────────────────────────────
def is_trading_closed():
    """当前是否已收盘（15:05之后）"""
    now = datetime.now()
    return (now.hour + now.minute / 60.0) >= 15.05


def get_today_is_trading_day():
    """用baostock判断今天是否为交易日"""
    try:
        import baostock as bs
        bs.login()
        today = datetime.now().strftime('%Y-%m-%d')
        rs = bs.query_trade_dates(start_date=today, end_date=today)
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        if rows and rows[0][1] == '1':  # is_trading_day='1'
            return True
    except Exception:
        pass
    return False


def get_previous_trading_date(today=None):
    """获取上一个交易日（不含今天），用baostock"""
    if today is None:
        today = datetime.now().strftime('%Y-%m-%d')
    try:
        import baostock as bs
        bs.login()
        start = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
        rs = bs.query_trade_dates(start_date=start, end_date=today)
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        # 找today之前最近的is_trading_day='1'
        for row in reversed(rows):
            if row[0] < today and row[1] == '1':
                return row[0]
    except Exception:
        pass
    # 降级：往前推1-2天（跳过周末）
    d = datetime.strptime(today, '%Y-%m-%d')
    for i in range(1, 8):
        prev = (d - timedelta(days=i)).strftime('%Y-%m-%d')
        wd = datetime.strptime(prev, '%Y-%m-%d').weekday()
        if wd < 5:  # 不是周末
            return prev
    return today


def get_report_date():
    """判断应生成哪一天的报告：
    - 交易日 + 盘后(>=15:05) → 今日
    - 盘中(<15:05) 或 非交易日 → 上一交易日
    """
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now()

    # 周末 → 非交易日
    if now.weekday() >= 5:
        prev = get_previous_trading_date(today)
        print(f"  📅 今日({today}周末)，生成上一交易日({prev})报告")
        return prev

    # 用baostock确认是否交易日
    is_trading = get_today_is_trading_day()

    if not is_trading:
        prev = get_previous_trading_date(today)
        print(f"  📅 今日({today}非交易日)，生成上一交易日({prev})报告")
        return prev

    # 交易日：盘后(>=15:05) → 今日；盘中 → 上一交易日
    if (now.hour + now.minute / 60.0) >= 15.05:
        print(f"  📅 今日({today}已收盘)，生成今日报告")
        return today
    else:
        prev = get_previous_trading_date(today)
        print(f"  📅 今日({today}盘中)，生成上一交易日({prev})报告")
        return prev


def _cache_path(name):
    return os.path.join(os.path.dirname(__file__), '..', 'cache', name)

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://gu.qq.com/'
}

# 腾讯行情API
TENCENT_QUOTE_URL = 'https://qt.gtimg.cn/q='


def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def _load_cache(name, max_age_hours=4):
    path = _cache_path(name)
    if os.path.exists(path):
        age = (time.time() - os.path.getmtime(path)) / 3600
        if age < max_age_hours:
            return pd.read_csv(path)
    return None


def _save_cache(name, df):
    if df is not None and len(df) > 0:
        df.to_csv(_cache_path(name), index=False)


def _get_stock_list():
    """获取A股代码列表（从腾讯全市场数据中提取）"""
    return None


def fetch_tencent_batch(codes, batch_size=60):
    """批量获取腾讯行情数据，返回DataFrame含'数据日期'字段（从parts[30]解析）"""
    all_data = []
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        # 转换代码格式: 确保补零到6位
        formatted = []
        for c in batch:
            c_str = str(c).zfill(6)  # 关键：补零！
            if c_str.startswith(('6',)):
                formatted.append(f'sh{c_str}')
            else:
                formatted.append(f'sz{c_str}')
        
        query = ','.join(formatted)
        url = f'{TENCENT_QUOTE_URL}{query}'
        
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            lines = r.text.strip().split(';')
            
            for line in lines:
                if '~' not in line or len(line) < 30:
                    continue
                parts = line.split('~')
                if len(parts) < 38:
                    continue
                
                try:
                    name = parts[1]
                    code = parts[2].zfill(6)  # 补零到6位
                    price = float(parts[3]) if parts[3] else 0
                    last_close = float(parts[4]) if parts[4] else 0
                    open_price = float(parts[5]) if parts[5] else 0
                    vol = float(parts[6]) if parts[6] else 0  # 成交量（手）
                    high = float(parts[33]) if parts[33] else 0
                    low = float(parts[34]) if parts[34] else 0
                    price_change = float(parts[31]) if parts[31] else 0
                    change_pct = float(parts[32]) if parts[32] else 0
                    turnover = float(parts[37]) if parts[37] else 0  # 成交额（万）
                    
                    # 从parts[30]解析数据日期，格式：20260515111658
                    raw_ts = parts[30] if len(parts) > 30 and parts[30] else ''
                    if raw_ts and len(raw_ts) >= 8:
                        data_date = f"{raw_ts[0:4]}-{raw_ts[4:6]}-{raw_ts[6:8]}"
                    else:
                        data_date = today_str  # 兜底：无法解析时用今天
                    
                    if price > 0:
                        all_data.append({
                            '代码': code,
                            '名称': name,
                            '最新价': price,
                            '昨收': last_close,
                            '今开': open_price,
                            '最高': high,
                            '最低': low,
                            '涨跌额': price_change,
                            '涨跌幅': change_pct,
                            '成交量': vol * 100,  # 手->股
                            '成交额': turnover * 10000,  # 万->元
                            '数据日期': data_date,  # 从腾讯时间戳提取
                        })
                except (ValueError, IndexError):
                    continue
            
            time.sleep(0.3)  # 避免请求过快
            
        except Exception as e:
            print(f"  ❌ 批次{i//batch_size+1}失败: {e}")
            continue
    
    return pd.DataFrame(all_data)


def get_all_stocks(date_str=None):
    """获取全A股行情。如果指定date_str，优先读取该日期的快照缓存。
    收盘后首次运行会生成快照，之后再跑同一日期直接读快照，结果一致。
    没有快照的历史日期无法获取数据，会报错退出。
    
    盘中（<15:05）取腾讯API数据：校验'数据日期'字段必须匹配目标日期，
    避免缓存过期或跨日数据干扰。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    now_h = datetime.now().hour + datetime.now().minute / 60.0
    is_trading_close = now_h >= 15.05  # 收盘后认为数据是当日确定的

    # 如果指定了日期，优先找该日期的快照
    if date_str:
        snapshot = _cache_path(f'snapshot_{date_str}.csv')
        if os.path.exists(snapshot):
            df = pd.read_csv(snapshot)
            print(f"  📦 使用日期快照 {date_str} ({len(df)}只)")
            return df
        # 没有快照，检查是不是今天（今天还可以从API拿）
        if date_str != today:
            # 无快照：用Tushare获取历史全市场行情
            print(f"  ⚠️ {date_str} 无快照，用Tushare重建历史排名...")
            df = _fetch_via_tushare(date_str)
            if df is not None and len(df) > 0:
                print(f"  📡 Tushare返回 {len(df)} 只，按成交额排序")
                df['数据降级'] = True
                return df
            raise ValueError(f"[{date_str}] Tushare无法获取该日数据。")
    
    # 缓存策略：收盘后(>15:05)缓存6小时；盘中缓存30分钟
    cache_age = 0.5 if not is_trading_close else 6
    cached = _load_cache('all_stocks_tencent.csv', max_age_hours=cache_age)
    if cached is not None:
        # 日期校验：盘中必须数据日期==today，历史日期快照直接用
        if date_str and not is_trading_close and '数据日期' in cached.columns:
            if cached['数据日期'].iloc[0] != date_str:
                print(f"  ⚠️ 缓存数据日期={cached['数据日期'].iloc[0]}，目标={date_str}，重新获取...")
            else:
                print(f"  📦 使用缓存({len(cached)}只, {cache_age}h有效)")
                if date_str:
                    _save_cache(f'snapshot_{date_str}.csv', cached)
                return cached
        else:
            print(f"  📦 使用缓存({len(cached)}只)")
            if date_str:
                _save_cache(f'snapshot_{date_str}.csv', cached)
            return cached
    
    # 先获取代码列表
    df = _fetch_all_from_api(date_str=date_str)
    if len(df) == 0:
        return df
    
    # 盘中严格校验数据日期
    if date_str and not is_trading_close and '数据日期' in df.columns:
        actual = df['数据日期'].iloc[0]
        if actual != date_str:
            raise ValueError(f"腾讯API返回数据日期={actual}，期望={date_str}，请确认当前时间是否已收盘或API状态")
    
    # 存缓存和快照
    _save_cache('all_stocks_tencent.csv', df)
    if date_str:
        _save_cache(f'snapshot_{date_str}.csv', df)
        print(f"  💾 已保存 {date_str} 快照 ({len(df)}只)")
    print(f"  ✅ 获取 {len(df)} 只活跃A股")
    return df


def _fetch_all_from_api(date_str=None):
    """从腾讯API获取全市场数据（不含缓存逻辑，纯API调用）"""
    print("  🌐 获取A股代码列表...")
    codes = _get_stock_list()
    
    if codes is None or len(codes) == 0:
        print("  🔄 使用备选代码列表...")
        codes = _generate_stock_codes()
    
    print(f"  📡 获取 {len(codes)} 只股票行情...")
    df = fetch_tencent_batch(codes)
    
    if len(df) == 0:
        print("  ❌ 获取失败")
        return pd.DataFrame()
    
    # 过滤
    df = df[df['最新价'] > 0]
    df = df[df['最新价'] < 200]
    df = df[~df['名称'].str.contains('ST|退|N', na=False)]
    df = df[df['成交额'] > 5e7]  # 5000万以上
    df = df.sort_values('成交额', ascending=False).reset_index(drop=True)
    return df


def _generate_stock_codes():
    """生成主要A股代码范围用于扫描"""
    codes = []
    # 沪市主板 600000-604999
    for i in range(600000, 605000):
        codes.append(str(i))
    # 深市主板 000001-004999
    for i in range(1, 5000):
        codes.append(f'{i:06d}')
    # 创业板 300000-301999
    for i in range(300000, 302000):
        codes.append(str(i))
    # 科创板 688000-689999
    for i in range(688000, 690000):
        codes.append(str(i))
    return codes


def get_stock_history(symbol, days=120, date_str=None):
    """获取个股日K线。baostock主力，搜狐降级。"""
    cache_name = f'hist_{symbol}.csv'
    cached = _load_cache(cache_name, max_age_hours=12)
    if cached is not None and len(cached) > 20:
        if date_str:
            truncated = _truncate_to_date(cached, date_str)
            if len(truncated) > 20:
                return truncated
        else:
            return cached
    
    # 主力: baostock
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code == '0':
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            end_d = date_str if date_str else datetime.now().strftime('%Y-%m-%d')
            start_d = (datetime.strptime(end_d, '%Y-%m-%d') - timedelta(days=180)).strftime('%Y-%m-%d')
            rs = bs.query_history_k_data_plus(
                f"{prefix}.{symbol}",
                "date,open,high,low,close,preclose,volume,amount,turn,pctChg",
                start_date=start_d, end_date=end_d,
                frequency="d", adjustflag="2")
            rows = []
            while (rs.error_code == '0') and rs.next():
                row = rs.get_row_data()
                if row[6]:  # volume不为空
                    rows.append({
                        '日期': row[0],
                        '开盘': float(row[1]),
                        '收盘': float(row[4]),
                        '最高': float(row[2]),
                        '最低': float(row[3]),
                        '涨跌额': float(row[4]) - float(row[5]) if row[5] else 0,
                        '涨跌幅': float(row[9]) if row[9] else 0,
                        '成交量': float(row[6]),
                        '成交额': float(row[7]) if row[7] else 0,
                        '换手率': float(row[8]) if row[8] else 0,
                        '振幅': ((float(row[2]) - float(row[3])) / float(row[5]) * 100) if row[5] and float(row[5]) > 0 else 0,
                    })
            bs.logout()
            if len(rows) > 10:
                df = pd.DataFrame(rows)
                _save_cache(cache_name, df)
                return _truncate_to_date(df, date_str)
    except Exception as e:
        print(f"  ⚠️ baostock查询失败 {symbol}: {e}")

    # 降级: 搜狐财经K线
    try:
        prefix = 'cn_' + symbol
        end_d = date_str.replace('-', '') if date_str else datetime.now().strftime('%Y%m%d')
        start_d = (datetime.strptime(end_d, '%Y%m%d') - timedelta(days=days)).strftime('%Y%m%d')
        url = f'https://q.stock.sohu.com/hisHq?code={prefix}&start={start_d}&end={end_d}&stat=1&order=D&period=d&callback='
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and '[' in r.text:
            import json as _json
            data = _json.loads(r.text)
            if data and len(data) > 0 and 'hq' in data[0]:
                hq = data[0]['hq']
                if len(hq) > 10:
                    rows = []
                    for item in reversed(hq):
                        pct_str = item[4].replace('%', '')
                        turnover_wan = float(item[8]) * 10000
                        rows.append({
                            '日期': item[0],
                            '开盘': float(item[1]),
                            '收盘': float(item[2]),
                            '涨跌额': float(item[3]),
                            '涨跌幅': float(pct_str),
                            '最低': float(item[5]),
                            '最高': float(item[6]),
                            '成交量': float(item[7]) * 100,  # 搜狐: 手->股
                            '成交额': turnover_wan,
                            '换手率': float(item[9].replace('%', '')),
                            '振幅': 0,
                        })
                    df = pd.DataFrame(rows)
                    _save_cache(cache_name, df)
                    return _truncate_to_date(df, date_str)
    except Exception as e:
        print(f"  ⚠️ 搜狐K线查询失败 {symbol}: {e}")

    return pd.DataFrame()


def _truncate_to_date(df, date_str):
    """将K线数据截断到指定日期（含），确保不会用到未来数据"""
    if date_str and '日期' in df.columns:
        df = df[df['日期'] <= date_str].copy()
    return df

def _fetch_via_tushare(date_str):
    """用Tushare获取历史全市场行情（成交额排名）。只含上证+深证，排除688科创板。"""
    import tushare as ts
    token = os.environ.get('TUSHARE_TOKEN', '')
    if not token:
        print("⚠️ 未设置 TUSHARE_TOKEN 环境变量，无法使用Tushare接口")
        return pd.DataFrame()
    trade_date = date_str.replace('-', '')
    pro = ts.pro_api(token)
    df = pro.daily(trade_date=trade_date, fields='ts_code,trade_date,open,high,low,close,vol,amount,pct_chg')
    if df is None or len(df) == 0:
        return pd.DataFrame()
    # 转换代码格式: 300502.SZ -> 300502, 600000.SH -> 600000（保持6位，不lstrip）
    df['代码'] = df['ts_code'].str.replace('.SZ', '').str.replace('.SH', '')
    # 只留上证(600/601/603开头)和深市(000/001/002/300开头)，排除688科创板
    df = df[df['代码'].str.match(r'^(600|601|603|000|001|002|300)')]
    df = df.rename(columns={
        'vol': '成交量',
        'amount': '成交额',
        'pct_chg': '涨跌幅',
        'open': '今开',
        'high': '最高',
        'low': '最低',
        'close': '最新价',
    })
    # Tushare vol=手(×100转股), amount=千元(×1000转元)
    df['成交量'] = df['成交量'] * 100
    df['成交额'] = df['成交额'] * 1000
    # 计算涨跌额（用昨收=前一日收盘，需要查前一交易日数据，这里直接省略）
    df['涨跌额'] = 0.0
    # 按成交额降序
    df = df.sort_values('成交额', ascending=False).reset_index(drop=True)
    # 补齐其他字段
    df['名称'] = df['代码']  # tushare不带名称，后续用baostock历史K线补
    df['数据日期'] = date_str  # 与腾讯数据保持一致
    return df


def get_top_volume_stocks(n=100, date_str=None):
    """获取成交额前N的活跃股"""
    df = get_all_stocks(date_str=date_str)
    if len(df) == 0:
        return df
    return df.head(n)


if __name__ == '__main__':
    print("获取全A股数据（腾讯行情API）...")
    df = get_all_stocks()
    print(f"共 {len(df)} 只股票")
    if len(df) > 0:
        print(df.head(15).to_string())
