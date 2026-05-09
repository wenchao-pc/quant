"""
A股量化选股系统 - 主入口
策略：多因子(均线+量价+连涨+支撑) 综合评分
数据源：腾讯行情API + AKShare日K线
"""
import sys
import os
import json
import time
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from data.fetcher import get_all_stocks, get_stock_history, get_top_volume_stocks
import pandas as pd
import numpy as np


def calc_ma(series, n):
    return series.rolling(window=n).mean()


def strategy_ma_breakthrough(df_hist):
    """均线突破 - MA5上穿MA20（金叉）"""
    if len(df_hist) < 30:
        return 0, {}
    close = df_hist['收盘']
    ma5 = calc_ma(close, 5)
    ma20 = calc_ma(close, 20)
    if len(ma5) < 3:
        return 0, {}
    
    prev_diff = ma5.iloc[-2] - ma20.iloc[-2]
    curr_diff = ma5.iloc[-1] - ma20.iloc[-1]
    score, info = 0, {}
    
    if prev_diff < 0 and curr_diff > 0:
        score = 80; info['signal'] = '金叉(MA5上穿MA20)'
    elif curr_diff > 0:
        score = 40; info['signal'] = '多头排列'
    else:
        score = 0; info['signal'] = '空头排列'
    
    if close.iloc[-1] > ma5.iloc[-1]:
        score += 10
    return min(score, 100), info


def strategy_volume_price(df_hist):
    """量价配合 - 放量上涨"""
    if len(df_hist) < 10:
        return 0, {}
    close = df_hist['收盘']
    volume = df_hist['成交量']
    vol_recent = volume.iloc[-5:].mean()
    vol_prev = volume.iloc[-10:-5].mean()
    if vol_prev == 0:
        return 0, {}
    
    vol_ratio = vol_recent / vol_prev
    pct_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100
    score, info = 0, {}
    
    if vol_ratio > 1.5 and pct_5d > 3:
        score = 80; info['signal'] = f'放量上涨({vol_ratio:.1f}倍量, 5日+{pct_5d:.1f}%)'
    elif vol_ratio > 1.2 and pct_5d > 0:
        score = 50; info['signal'] = f'温和放量({vol_ratio:.1f}倍量, 5日+{pct_5d:.1f}%)'
    elif vol_ratio < 0.8 and pct_5d > 2:
        score = 30; info['signal'] = f'缩量上涨({vol_ratio:.1f}倍量)'
    return min(score, 100), info


def strategy_consecutive_up(df_hist):
    """连涨形态"""
    if len(df_hist) < 5:
        return 0, {}
    close = df_hist['收盘']
    changes = close.pct_change().iloc[-5:]
    consec = 0
    for i in range(len(changes)-1, -1, -1):
        if changes.iloc[i] > 0:
            consec += 1
        else:
            break
    
    score, info = 0, {}
    if consec >= 5:
        score = 50; info['signal'] = f'连涨{consec}天(注意回调)'
    elif consec == 4:
        score = 90; info['signal'] = f'连涨{consec}天(强势)'
    elif consec == 3:
        score = 70; info['signal'] = '连涨3天'
    elif consec == 2:
        score = 40; info['signal'] = '连涨2天'
    return score, info


def strategy_support_bounce(df_hist):
    """支撑位反弹 - MA60附近反弹"""
    if len(df_hist) < 65:
        return 0, {}
    close = df_hist['收盘']
    ma60 = calc_ma(close, 60)
    ma20 = calc_ma(close, 20)
    curr_close = close.iloc[-1]
    curr_ma60 = ma60.iloc[-1]
    if curr_ma60 == 0:
        return 0, {}
    
    ratio = (curr_close / curr_ma60 - 1) * 100
    score, info = 0, {}
    
    if -3 < ratio < 2 and close.iloc[-1] > close.iloc[-2]:
        score = 75; info['signal'] = f'MA60支撑反弹(偏离{ratio:.1f}%)'
    elif ratio > 2 and curr_close > ma20.iloc[-1]:
        score = 50; info['signal'] = '站稳均线上方'
    return score, info


def analyze_stock(code, name, price, change_pct, turnover):
    """对单只股票运行所有策略"""
    df_hist = get_stock_history(code)
    if len(df_hist) < 30:
        return None
    
    scores = {}
    details = {}
    
    for strat_name, strat_fn in [
        ('均线突破', strategy_ma_breakthrough),
        ('量价配合', strategy_volume_price),
        ('连涨形态', strategy_consecutive_up),
        ('支撑反弹', strategy_support_bounce),
    ]:
        s, d = strat_fn(df_hist)
        scores[strat_name] = s
        details[strat_name] = d
    
    weights = {'均线突破': 0.3, '量价配合': 0.3, '连涨形态': 0.25, '支撑反弹': 0.15}
    total = sum(scores[k] * weights[k] for k in weights)
    
    return {
        'code': code,
        'name': name,
        'price': price,
        'change_pct': change_pct,
        'turnover': turnover,
        'total_score': round(total, 1),
        'scores': scores,
        'details': details,
    }


def run_daily_screening(top_n=80):
    """每日选股主函数"""
    start_time = time.time()
    print(f"{'='*60}")
    print(f"📊 A股量化选股系统")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 1. 获取活跃股池
    print(f"\n🔍 获取成交额前{top_n}活跃股...")
    df = get_top_volume_stocks(top_n)
    if len(df) == 0:
        print("❌ 无法获取行情数据")
        return []
    print(f"  ✅ 候选股: {len(df)} 只\n")
    
    # 2. 逐只分析
    results = []
    total = len(df)
    
    for idx, (_, row) in enumerate(df.iterrows()):
        code = str(row['代码']).zfill(6)  # 确保补零
        name = row['名称']
        price = row['最新价']
        change_pct = row.get('涨跌幅', 0)
        turnover = row.get('成交额', 0)
        
        print(f"  [{idx+1}/{total}] 分析 {name}({code})...", end='')
        
        try:
            result = analyze_stock(code, name, price, change_pct, turnover)
            if result and result['total_score'] >= 70:
                results.append(result)
                print(f" ✅ 得分:{result['total_score']}")
            else:
                score = result['total_score'] if result else 0
                print(f" ⬜ 得分:{score}")
        except Exception as e:
            print(f" ❌ 错误")
        
        # 控制节奏
        if idx % 10 == 9:
            time.sleep(0.5)
    
    # 3. 排序输出
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ 耗时: {elapsed:.0f}秒")
    print(f"📊 入选: {len(results)} 只 (得分≥70)")
    
    return results


def format_report(results, top=15):
    """格式化选股报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    lines = [f"📈 A股量化选股报告 | {now}"]
    lines.append(f"{'='*55}")
    
    if not results:
        lines.append("❌ 今日无符合条件的股票")
        return '\n'.join(lines)
    
    lines.append(f"🎯 筛选结果: {len(results)} 只入选（得分≥70），展示Top{min(top, len(results))}")
    lines.append("")
    
    for i, r in enumerate(results[:top]):
        medal = ['🥇', '🥈', '🥉'][i] if i < 3 else f' {i+1}.'
        turnover_yi = r['turnover'] / 1e8
        
        lines.append(f"{medal} {r['name']}({r['code']}) | 得分:{r['total_score']}")
        lines.append(f"   💰 价格:{r['price']:.2f} | 涨跌:{r['change_pct']:+.2f}% | 成交:{turnover_yi:.1f}亿")
        
        signals = []
        for strat, score in r['scores'].items():
            if score > 0:
                sig = r['details'][strat].get('signal', '')
                signals.append(f"{strat}:{score}分({sig})")
        if signals:
            lines.append(f"   📊 {' | '.join(signals[:3])}")
        lines.append("")
    
    lines.append(f"{'='*55}")
    lines.append("⚠️ 量化分析仅供参考，不构成投资建议")
    lines.append("💡 建议结合大盘趋势、板块热点和个人判断")
    
    return '\n'.join(lines)


def save_results(results):
    """保存结果到JSON"""
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    date_str = datetime.now().strftime('%Y%m%d_%H%M')
    path = os.path.join(output_dir, f'stock_picks_{date_str}.json')
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"💾 结果已保存: {path}")
    return path


if __name__ == '__main__':
    results = run_daily_screening(top_n=80)
    report = format_report(results, top=15)
    print("\n" + report)
    
    if results:
        save_results(results)
