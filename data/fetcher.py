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
    """批量获取腾讯行情数据"""
    all_data = []
    
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
    """
    # 如果指定了日期，优先找该日期的快照
    if date_str:
        snapshot = _cache_path(f'snapshot_{date_str}.csv')
        if os.path.exists(snapshot):
            df = pd.read_csv(snapshot)
            print(f"  📦 使用日期快照 {date_str} ({len(df)}只)")
            return df
        # 没有快照，检查是不是今天（今天还可以从API拿）
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        if date_str != today:
            print(f"  ⚠️ {date_str} 无快照数据，降级方案：用当前排名 + baostock历史K线")
            # 降级：用当前API拿全市场数据（排名可能不准），标记为降级
            df = _fetch_all_from_api()
            if len(df) > 0:
                df['数据降级'] = True
            return df
    
    cached = _load_cache('all_stocks_tencent.csv', max_age_hours=6)
    if cached is not None:
        print(f"  📦 使用缓存({len(cached)}只)")
        # 如果指定了日期（=今天），把当前缓存存为快照
        if date_str:
            _save_cache(f'snapshot_{date_str}.csv', cached)
        return cached
    
    # 先获取代码列表
    df = _fetch_all_from_api()
    if len(df) == 0:
        return df
    # 存缓存和快照
    _save_cache('all_stocks_tencent.csv', df)
    if date_str:
        _save_cache(f'snapshot_{date_str}.csv', df)
        print(f"  💾 已保存 {date_str} 快照 ({len(df)}只)")
    print(f"  ✅ 获取 {len(df)} 只活跃A股")
    return df


def _fetch_all_from_api():
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
                            '成交量': float(item[7]),
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
