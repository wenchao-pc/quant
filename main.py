"""
A股量化选股系统 - 主入口
策略：多因子(MACD+均线+量价+KDJ+RSI+布林+连涨+支撑) 综合评分
数据源：baostock 前复权日K线
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


def calc_ema(series, n):
    """计算指数移动平均线"""
    return series.ewm(span=n, adjust=False).mean()


# ============================================================
# 策略1: MACD（DIF/DEA金叉死叉）
# ============================================================
def strategy_macd(df_hist):
    """MACD策略 - DIF上穿DEA(金叉)高分, 零轴上方金叉更高分, 死叉0分"""
    if len(df_hist) < 40:
        return 0, {}

    close = df_hist['收盘']
    ema12 = calc_ema(close, 12)
    ema26 = calc_ema(close, 26)
    dif = ema12 - ema26
    dea = calc_ema(dif, 9)
    macd_bar = (dif - dea) * 2  # MACD柱

    score, info = 0, {}

    # 当前与前一日的DIF/DEA关系
    curr_dif, prev_dif = dif.iloc[-1], dif.iloc[-2]
    curr_dea, prev_dea = dea.iloc[-1], dea.iloc[-2]

    # 判断金叉/死叉
    golden_cross = prev_dif <= prev_dea and curr_dif > curr_dea
    death_cross = prev_dif >= prev_dea and curr_dif < curr_dea
    dif_above_zero = curr_dif > 0
    curr_bar = macd_bar.iloc[-1]

    if golden_cross and dif_above_zero:
        score = 95
        info['signal'] = '零轴上方金叉(强势)'
    elif golden_cross:
        score = 75
        info['signal'] = '零轴下方金叉'
    elif death_cross:
        score = 0
        info['signal'] = '死叉'
    elif curr_dif > curr_dea and dif_above_zero:
        # DIF在DEA上方且在零轴上方 - 多头趋势
        # MACD柱在增长则加分
        if len(macd_bar) >= 3 and macd_bar.iloc[-1] > macd_bar.iloc[-2]:
            score = 70
            info['signal'] = '多头趋势(红柱增长)'
        else:
            score = 50
            info['signal'] = '多头趋势(红柱缩短)'
    elif curr_dif > curr_dea:
        score = 35
        info['signal'] = 'DIF>DEA(零轴下方)'
    else:
        score = 0
        info['signal'] = '空头'

    info['dif'] = round(curr_dif, 4)
    info['dea'] = round(curr_dea, 4)
    info['macd'] = round(curr_bar, 4)
    return min(max(score, 0), 100), info


# ============================================================
# 策略2: 均线突破（原策略保留）
# ============================================================
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


# ============================================================
# 策略3: 量价配合（原策略保留）
# ============================================================
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


# ============================================================
# 策略4: KDJ
# ============================================================
def strategy_kdj(df_hist):
    """KDJ策略 - J值从超卖区上穿加分, 超买区死叉减分"""
    if len(df_hist) < 20:
        return 0, {}

    close = df_hist['收盘']
    high = df_hist['最高']
    low = df_hist['最低']
    n = 9

    score, info = 0, {}

    # 计算KDJ
    lowest_low = low.rolling(window=n).min()
    highest_high = high.rolling(window=n).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    rsv = rsv.fillna(50)  # 避免除零

    # 用EMA平滑得到K, D
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d

    curr_k, prev_k = k.iloc[-1], k.iloc[-2]
    curr_d, prev_d = d.iloc[-1], d.iloc[-2]
    curr_j, prev_j = j.iloc[-1], j.iloc[-2]

    golden_cross = prev_k <= prev_d and curr_k > curr_d
    death_cross = prev_k >= prev_d and curr_k < curr_d

    if golden_cross and prev_j < 20:
        # 超卖区金叉 - 最佳买入信号
        score = 90
        info['signal'] = f'超卖区金叉(J:{prev_j:.1f}→{curr_j:.1f})'
    elif golden_cross and curr_j < 50:
        score = 70
        info['signal'] = f'低位金叉(J:{curr_j:.1f})'
    elif golden_cross:
        score = 45
        info['signal'] = f'金叉(J:{curr_j:.1f})'
    elif death_cross and prev_j > 80:
        # 超买区死叉 - 减分
        score = 0
        info['signal'] = f'超买区死叉(J:{prev_j:.1f}→{curr_j:.1f})'
    elif death_cross:
        score = 10
        info['signal'] = f'死叉(J:{curr_j:.1f})'
    else:
        # 未交叉时按J值位置评分
        if 20 <= curr_j <= 80:
            if curr_j > prev_j:
                score = 55
                info['signal'] = f'J值上升({curr_j:.1f})'
            else:
                score = 35
                info['signal'] = f'J值回落({curr_j:.1f})'
        elif curr_j > 80:
            score = 20
            info['signal'] = f'J值超买({curr_j:.1f})'
        else:
            score = 40
            info['signal'] = f'J值超卖区({curr_j:.1f})'

    info['k'] = round(curr_k, 2)
    info['d'] = round(curr_d, 2)
    info['j'] = round(curr_j, 2)
    return min(max(score, 0), 100), info


# ============================================================
# 策略5: RSI
# ============================================================
def strategy_rsi(df_hist):
    """RSI策略 - RSI14在40-60区间且上升加分, >70超买减分, <30超卖反弹加分"""
    if len(df_hist) < 20:
        return 0, {}

    close = df_hist['收盘']
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    period = 14
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # 避免除零
    avg_loss = avg_loss.replace(0, np.nan)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)  # 无损失时RSI=100, 填充为50保守处理

    if len(rsi) < 3:
        return 0, {}

    curr_rsi = rsi.iloc[-1]
    prev_rsi = rsi.iloc[-2]

    score, info = 0, {}

    if 40 <= curr_rsi <= 60:
        # 健康区间
        if curr_rsi > prev_rsi:
            score = 75
            info['signal'] = f'RSI健康区间上升({curr_rsi:.1f})'
        else:
            score = 55
            info['signal'] = f'RSI健康区间({curr_rsi:.1f})'
    elif 60 < curr_rsi <= 70:
        # 偏强但未超买
        score = 60
        info['signal'] = f'RSI偏强({curr_rsi:.1f})'
    elif curr_rsi > 70:
        # 超买区
        if curr_rsi > 85:
            score = 10
            info['signal'] = f'RSI严重超买({curr_rsi:.1f})'
        else:
            score = 25
            info['signal'] = f'RSI超买({curr_rsi:.1f})'
    elif 30 <= curr_rsi < 40:
        # 偏弱但有反弹机会
        if curr_rsi > prev_rsi:
            score = 60
            info['signal'] = f'RSI弱势反弹({curr_rsi:.1f})'
        else:
            score = 30
            info['signal'] = f'RSI偏弱({curr_rsi:.1f})'
    else:
        # RSI < 30 超卖区
        if curr_rsi > prev_rsi:
            # 超卖反弹信号
            score = 80
            info['signal'] = f'RSI超卖反弹({curr_rsi:.1f})'
        else:
            score = 20
            info['signal'] = f'RSI超卖({curr_rsi:.1f})'

    info['rsi14'] = round(curr_rsi, 2)
    return min(max(score, 0), 100), info


# ============================================================
# 策略6: 布林带
# ============================================================
def strategy_bollinger(df_hist):
    """布林带策略 - 突破上轨高分, 中轨支撑加分, 下轨破位减分"""
    if len(df_hist) < 25:
        return 0, {}

    close = df_hist['收盘']
    volume = df_hist['成交量']
    period = 20

    mid = close.rolling(window=period).mean()        # 中轨=MA20
    std = close.rolling(window=period).std()          # 标准差
    upper = mid + 2 * std                             # 上轨
    lower = mid - 2 * std                             # 下轨

    if len(upper) < 3 or pd.isna(upper.iloc[-1]):
        return 0, {}

    curr_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    curr_upper = upper.iloc[-1]
    prev_upper = upper.iloc[-2]
    curr_lower = lower.iloc[-1]
    prev_lower = lower.iloc[-2]
    curr_mid = mid.iloc[-1]
    prev_mid = mid.iloc[-2]

    score, info = 0, {}

    # 判断带宽（缩口/扩口）
    curr_bandwidth = curr_upper - curr_lower
    prev_bandwidth = prev_upper - prev_lower
    narrowing = curr_bandwidth < prev_bandwidth  # 缩口

    # 量比
    if len(volume) >= 10 and volume.iloc[-6:-1].mean() > 0:
        vol_ratio = volume.iloc[-1] / volume.iloc[-6:-1].mean()
    else:
        vol_ratio = 1.0

    if curr_close > curr_upper:
        # 突破上轨
        if narrowing and vol_ratio > 1.5:
            # 缩口后放量突破 - 强信号
            score = 90
            info['signal'] = f'缩口放量突破上轨(量比{vol_ratio:.1f})'
        elif vol_ratio > 1.3:
            score = 70
            info['signal'] = f'放量突破上轨(量比{vol_ratio:.1f})'
        else:
            score = 50
            info['signal'] = '触及上轨'
    elif curr_close > curr_mid:
        # 中轨上方
        if prev_close <= prev_mid and curr_close > curr_mid:
            # 站上中轨
            score = 70
            info['signal'] = '突破中轨'
        elif prev_close > prev_mid:
            score = 55
            info['signal'] = '中轨上方运行'
        else:
            score = 40
            info['signal'] = '中轨附近'
    elif curr_close > curr_lower:
        # 中轨与下轨之间
        if curr_close > prev_close and prev_close < prev_lower:
            # 从下轨反弹
            score = 60
            info['signal'] = '下轨反弹'
        else:
            score = 25
            info['signal'] = '中下轨之间(偏弱)'
    else:
        # 跌破下轨
        score = 5
        info['signal'] = '跌破下轨'

    info['upper'] = round(curr_upper, 2)
    info['mid'] = round(curr_mid, 2)
    info['lower'] = round(curr_lower, 2)
    info['bandwidth'] = round(curr_bandwidth, 3)
    return min(max(score, 0), 100), info


# ============================================================
# 策略7: 连涨形态（修复bug）
# ============================================================
def strategy_consecutive_up(df_hist):
    """连涨形态 - 连涨天数越多分数越高, 5天以上注意回调风险"""
    if len(df_hist) < 10:
        return 0, {}
    close = df_hist['收盘']
    # 检查最近10天的连涨
    changes = close.pct_change().iloc[-10:]
    consec = 0
    for i in range(len(changes) - 1, -1, -1):
        if changes.iloc[i] > 0:
            consec += 1
        else:
            break

    score, info = 0, {}
    if consec >= 6:
        score = 60  # 连涨太多有回调风险，降分
        info['signal'] = f'连涨{consec}天(注意回调风险)'
    elif consec == 5:
        score = 75  # 强势但有风险
        info['signal'] = '连涨5天(强势,注意回调)'
    elif consec == 4:
        score = 85
        info['signal'] = '连涨4天(强势)'
    elif consec == 3:
        score = 70
        info['signal'] = '连涨3天'
    elif consec == 2:
        score = 45
        info['signal'] = '连涨2天'
    elif consec == 1:
        score = 20
        info['signal'] = '连涨1天'
    else:
        score = 0
        info['signal'] = '未连涨'
    return score, info


# ============================================================
# 策略8: 支撑反弹（原策略保留）
# ============================================================
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


def analyze_stock(code, name, price, change_pct, turnover, date_str=None):
    """对单只股票运行所有策略"""
    df_hist = get_stock_history(code, date_str=date_str)
    if len(df_hist) < 30:
        return None

    scores = {}
    details = {}

    for strat_name, strat_fn in [
        ('MACD', strategy_macd),
        ('均线突破', strategy_ma_breakthrough),
        ('量价配合', strategy_volume_price),
        ('KDJ', strategy_kdj),
        ('RSI', strategy_rsi),
        ('布林带', strategy_bollinger),
        ('连涨形态', strategy_consecutive_up),
        ('支撑反弹', strategy_support_bounce),
    ]:
        s, d = strat_fn(df_hist)
        scores[strat_name] = s
        details[strat_name] = d

    weights = {
        'MACD':    0.20,
        '均线突破': 0.15,
        '量价配合': 0.15,
        'KDJ':     0.15,
        'RSI':     0.10,
        '布林带':  0.10,
        '连涨形态': 0.10,
        '支撑反弹': 0.05,
    }
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


def run_daily_screening(top_n=40, date_str=None, THRESHOLD=70):
    """每日选股主函数"""
    start_time = time.time()
    print(f"{'='*60}")
    print(f"📊 A股量化选股系统")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 1. 获取活跃股池
    print(f"\n🔍 获取成交额前{top_n}活跃股...")
    df = get_top_volume_stocks(top_n, date_str=date_str)
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
            result = analyze_stock(code, name, price, change_pct, turnover, date_str=date_str)
            if result and result['total_score'] >= THRESHOLD:
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
    # 判断应生成哪天的报告
    from data.fetcher import get_report_date
    report_date = get_report_date()
    results = run_daily_screening(top_n=80, date_str=report_date)
    report = format_report(results, top=15)
    print("\n" + report)

    if results:
        save_results(results)
