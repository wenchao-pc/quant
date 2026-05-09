"""
A股多因子选股策略
策略组合：动量 + 均线突破 + 量价配合 + 连涨形态
"""
import pandas as pd
import numpy as np
from data.fetcher import get_all_stocks, get_stock_history, get_top_volume_stocks


def calc_ma(series, n):
    """计算移动平均线"""
    return series.rolling(window=n).mean()


def strategy_ma_breakthrough(df_hist):
    """
    策略1：均线突破 - MA5上穿MA20（金叉）
    返回得分 0-100
    """
    if len(df_hist) < 30:
        return 0, {}
    
    close = df_hist['收盘']
    ma5 = calc_ma(close, 5)
    ma20 = calc_ma(close, 20)
    
    # 金叉信号：前1天MA5<MA20，今天MA5>MA20
    if len(ma5) < 3 or len(ma20) < 3:
        return 0, {}
    
    prev_diff = ma5.iloc[-2] - ma20.iloc[-2]
    curr_diff = ma5.iloc[-1] - ma20.iloc[-1]
    
    score = 0
    info = {}
    
    # 金叉
    if prev_diff < 0 and curr_diff > 0:
        score = 80
        info['signal'] = '金叉(MA5上穿MA20)'
    # MA5 > MA20 多头排列
    elif curr_diff > 0:
        score = 40
        info['signal'] = '多头排列'
    # MA5 < MA20 空头
    else:
        score = 0
        info['signal'] = '空头排列'
    
    # 股价站在MA5之上加分
    if close.iloc[-1] > ma5.iloc[-1]:
        score += 10
    
    return min(score, 100), info


def strategy_volume_price(df_hist):
    """
    策略2：量价配合 - 放量上涨
    """
    if len(df_hist) < 10:
        return 0, {}
    
    close = df_hist['收盘']
    volume = df_hist['成交量']
    
    # 近5日平均成交量 vs 前5日平均成交量
    vol_recent = volume.iloc[-5:].mean()
    vol_prev = volume.iloc[-10:-5].mean()
    
    if vol_prev == 0:
        return 0, {}
    
    vol_ratio = vol_recent / vol_prev
    
    # 近5日涨幅
    pct_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100
    
    score = 0
    info = {}
    
    # 放量 + 上涨
    if vol_ratio > 1.5 and pct_5d > 3:
        score = 80
        info['signal'] = f'放量上涨({vol_ratio:.1f}倍量, 5日+{pct_5d:.1f}%)'
    elif vol_ratio > 1.2 and pct_5d > 0:
        score = 50
        info['signal'] = f'温和放量({vol_ratio:.1f}倍量, 5日+{pct_5d:.1f}%)'
    elif vol_ratio < 0.8 and pct_5d > 2:
        score = 30
        info['signal'] = f'缩量上涨({vol_ratio:.1f}倍量)'
    
    return min(score, 100), info


def strategy_consecutive_up(df_hist):
    """
    策略3：连涨形态 - 连续上涨天数
    """
    if len(df_hist) < 5:
        return 0, {}
    
    close = df_hist['收盘']
    changes = close.pct_change().iloc[-5:] * 100
    
    # 计算连涨天数
    consec = 0
    for i in range(len(changes)-1, -1, -1):
        if changes.iloc[i] > 0:
            consec += 1
        else:
            break
    
    score = 0
    info = {}
    
    if consec >= 4:
        score = 90
        info['signal'] = f'连涨{consec}天(强势)'
    elif consec == 3:
        score = 70
        info['signal'] = '连涨3天'
    elif consec == 2:
        score = 40
        info['signal'] = '连涨2天'
    
    # 但如果连涨太多（5天+），要注意回调风险
    if consec >= 5:
        score = 50  # 降低分数
        info['signal'] += '(注意回调)'
    
    return score, info


def strategy_support_bounce(df_hist):
    """
    策略4：支撑位反弹 - 跌到MA60附近反弹
    """
    if len(df_hist) < 65:
        return 0, {}
    
    close = df_hist['收盘']
    ma60 = calc_ma(close, 60)
    ma20 = calc_ma(close, 20)
    
    curr_close = close.iloc[-1]
    curr_ma60 = ma60.iloc[-1]
    curr_ma20 = ma20.iloc[-1]
    
    if curr_ma60 == 0:
        return 0, {}
    
    score = 0
    info = {}
    
    # 股价接近MA60（在±3%范围内）
    ratio = (curr_close / curr_ma60 - 1) * 100
    
    if -3 < ratio < 2 and close.iloc[-1] > close.iloc[-2]:
        score = 75
        info['signal'] = f'MA60支撑反弹(偏离{ratio:.1f}%)'
    elif ratio > 2 and curr_close > curr_ma20:
        score = 50
        info['signal'] = '站稳均线上方'
    
    return score, info


def run_stock_analysis(code, name):
    """对单只股票运行所有策略，返回综合得分"""
    df_hist = get_stock_history(code)
    if len(df_hist) < 30:
        return None
    
    scores = {}
    details = {}
    
    # 运行各策略
    s1, d1 = strategy_ma_breakthrough(df_hist)
    scores['均线突破'] = s1
    details['均线突破'] = d1
    
    s2, d2 = strategy_volume_price(df_hist)
    scores['量价配合'] = s2
    details['量价配合'] = d2
    
    s3, d3 = strategy_consecutive_up(df_hist)
    scores['连涨形态'] = s3
    details['连涨形态'] = d3
    
    s4, d4 = strategy_support_bounce(df_hist)
    scores['支撑反弹'] = s4
    details['支撑反弹'] = d4
    
    # 综合加权得分
    weights = {
        '均线突破': 0.3,
        '量价配合': 0.3,
        '连涨形态': 0.25,
        '支撑反弹': 0.15,
    }
    
    total = sum(scores[k] * weights[k] for k in weights)
    
    # 获取当前行情信息
    latest = df_hist.iloc[-1]
    
    return {
        'code': code,
        'name': name,
        'price': latest['收盘'],
        'change_pct': latest['涨跌幅'],
        'total_score': round(total, 1),
        'scores': scores,
        'details': details,
    }


def run_daily_screening(top_n=100):
    """
    每日选股主函数
    从成交额前N的股票中筛选
    """
    print(f"📊 获取成交额前{top_n}活跃股...")
    df_active = get_top_volume_stocks(top_n)
    print(f"  共 {len(df_active)} 只候选股")
    
    results = []
    for i, row in df_active.iterrows():
        code = row['代码']
        name = row['名称']
        
        try:
            result = run_stock_analysis(code, name)
            if result and result['total_score'] >= 50:
                results.append(result)
                print(f"  ✅ {name}({code}) 综合得分: {result['total_score']}")
        except Exception as e:
            pass
    
    # 按综合得分排序
    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results


def format_results(results, top=10):
    """格式化输出选股结果"""
    if not results:
        return "❌ 今日无符合条件的股票"
    
    lines = []
    lines.append(f"📈 A股量化选股报告")
    lines.append(f"📅 分析时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"🔍 筛选结果: {len(results)} 只入选，展示前{min(top, len(results))}只\n")
    
    for i, r in enumerate(results[:top]):
        lines.append(f"{'='*50}")
        lines.append(f"🥇 第{i+1}名 | {r['name']}({r['code']}) | 综合得分: {r['total_score']}")
        lines.append(f"   最新价: {r['price']:.2f} | 今日涨跌: {r['change_pct']:.2f}%")
        
        for strategy, score in r['scores'].items():
            if score > 0:
                detail = r['details'][strategy].get('signal', '')
                lines.append(f"   ├ {strategy}: {score}分 - {detail}")
        lines.append("")
    
    lines.append(f"{'='*50}")
    lines.append("⚠️ 以上为量化策略分析结果，不构成投资建议")
    lines.append("💡 建议结合大盘趋势和个人判断操作")
    
    return '\n'.join(lines)


if __name__ == '__main__':
    results = run_daily_screening(top_n=100)
    report = format_results(results, top=15)
    print(report)
