"""
A股量化策略历史回测
模拟过去N个交易日的选股，追踪买入后1-5天的涨跌幅，计算胜率和收益
"""
import sys
import os
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from data.fetcher import get_stock_history, get_all_stocks
import pandas as pd
import numpy as np
from main import (
    calc_ma, strategy_ma_breakthrough, strategy_volume_price,
    strategy_consecutive_up, strategy_support_bounce
)


def analyze_stock_at_date(df_hist, end_idx):
    """在历史某个时间点分析股票（用end_idx截断数据）"""
    df_cut = df_hist.iloc[:end_idx+1].copy()
    if len(df_cut) < 30:
        return None
    
    scores = {}
    for strat_name, strat_fn in [
        ('均线突破', strategy_ma_breakthrough),
        ('量价配合', strategy_volume_price),
        ('连涨形态', strategy_consecutive_up),
        ('支撑反弹', strategy_support_bounce),
    ]:
        s, _ = strat_fn(df_cut)
        scores[strat_name] = s
    
    weights = {'均线突破': 0.3, '量价配合': 0.3, '连涨形态': 0.25, '支撑反弹': 0.15}
    total = sum(scores[k] * weights[k] for k in weights)
    
    return round(total, 1)


def run_backtest(test_days=20, top_n=50, score_threshold=50):
    """
    回测主函数
    
    参数:
        test_days: 回测多少个交易日
        top_n: 每次从成交额前多少只里选
        score_threshold: 策略得分阈值
        
    逻辑:
        对于每个历史交易日:
        1. 用该日之前的K线数据跑策略
        2. 筛选出得分≥阈值的股票
        3. 记录这些股票在之后1-5天的涨跌幅
        4. 统计胜率和平均收益
    """
    print("=" * 60)
    print(f"📊 A股量化策略回测")
    print(f"📅 回测期: 最近{test_days}个交易日")
    print(f"🎯 策略阈值: 得分≥{score_threshold}")
    print(f"🔍 选股范围: 成交额前{top_n}")
    print("=" * 60)
    
    # 1. 获取活跃股票列表
    print("\n📡 获取股票列表...")
    df_all = get_all_stocks()
    if len(df_all) == 0:
        print("❌ 无法获取股票列表")
        return
    
    # 取成交额前top_n
    df_pool = df_all.head(top_n)
    codes = [str(c).zfill(6) for c in df_pool['代码'].tolist()]
    print(f"  ✅ 候选股: {len(codes)} 只")
    
    # 2. 批量获取K线数据
    print(f"\n📈 下载K线数据（{len(codes)}只，需要几分钟）...")
    stock_data = {}
    for i, code in enumerate(codes):
        name = df_pool.iloc[i]['名称'] if i < len(df_pool) else code
        df_hist = get_stock_history(code)
        if len(df_hist) > 60:
            stock_data[code] = {'name': name, 'df': df_hist}
        if (i+1) % 10 == 0:
            print(f"  [{i+1}/{len(codes)}] 已下载 {len(stock_data)} 只有效数据")
        time.sleep(0.1)
    
    print(f"  ✅ 有效数据: {len(stock_data)} 只")
    
    if len(stock_data) < 10:
        print("❌ 有效数据太少")
        return
    
    # 3. 找到共同的交易日
    all_dates = None
    for code, info in stock_data.items():
        dates = set(info['df']['日期'].tolist())
        if all_dates is None:
            all_dates = dates
        else:
            all_dates = all_dates & dates
    
    all_dates = sorted(list(all_dates))
    print(f"  📅 共同交易日: {len(all_dates)} 天")
    
    if len(all_dates) < test_days + 10:
        print(f"❌ 交易日不够（需要{test_days+10}天，实际{len(all_dates)}天）")
        test_days = max(len(all_dates) - 10, 5)
        print(f"  📉 调整为回测{test_days}天")
    
    # 4. 逐日回测
    print(f"\n🔄 开始回测...")
    
    all_trades = []  # 所有交易记录
    
    # 从倒数第(test_days+5)天开始回测（留5天看后续表现）
    start_idx = len(all_dates) - test_days - 5
    end_idx = len(all_dates) - 5  # 最后5天用来计算收益
    
    for day_i in range(start_idx, end_idx):
        test_date = all_dates[day_i]
        
        # 在这个日期，对每只股票跑策略
        day_picks = []
        for code, info in stock_data.items():
            df = info['df']
            # 找到该日期在df中的位置
            date_mask = df['日期'] == test_date
            if not date_mask.any():
                continue
            
            df_idx = df[date_mask].index[0]
            
            # 用这个日期之前的数据跑策略
            score = analyze_stock_at_date(df, df_idx)

            if score is not None and score >= score_threshold:
                # 记录当天价格
                price_today = df.loc[df_idx, '收盘']
                change_today = df.loc[df_idx, '涨跌幅'] if '涨跌幅' in df.columns else 0

                day_picks.append({
                    'code': code,
                    'name': info['name'],
                    'score': score,
                    'price': price_today,
                    'change_today': change_today,
                    'test_date': test_date,  # 用日期字符串而非整数索引
                })

        # 按得分排序取前5
        day_picks.sort(key=lambda x: x['score'], reverse=True)
        day_picks = day_picks[:5]

        if not day_picks:
            continue

        # 计算后续收益（用交易日历查找未来日期，避免非交易日跳跃问题）
        for pick in day_picks:
            df = stock_data[pick['code']]['df']
            test_date = pick['test_date']
            buy_price = pick['price']

            trade = {
                'date': test_date,
                'code': pick['code'],
                'name': pick['name'],
                'score': pick['score'],
                'buy_price': buy_price,
                'change_today': pick['change_today'],
            }

            # 用 all_dates 查找未来第 N 个交易日
            try:
                test_day_idx = all_dates.index(test_date)
            except ValueError:
                continue

            for hold_days in [1, 2, 3, 5]:
                future_day_idx = test_day_idx + hold_days
                if future_day_idx < len(all_dates):
                    future_date = all_dates[future_day_idx]
                    date_mask = df['日期'] == future_date
                    if date_mask.any():
                        future_price = df.loc[date_mask, '收盘'].iloc[0]
                        ret = (future_price / buy_price - 1) * 100
                        trade[f'return_{hold_days}d'] = round(ret, 2)
                    else:
                        trade[f'return_{hold_days}d'] = None
                else:
                    trade[f'return_{hold_days}d'] = None

            all_trades.append(trade)
        
        picked_names = [p['name'] for p in day_picks[:3]]
        print(f"  {test_date} | 选出{len(day_picks)}只 | {', '.join(picked_names)}")
    
    # 5. 统计结果
    print(f"\n{'='*60}")
    print(f"📊 回测结果统计")
    print(f"{'='*60}")
    
    if not all_trades:
        print("❌ 无交易记录")
        return
    
    total_trades = len(all_trades)
    
    # 按持有天数统计
    summary_lines = []
    for hold_days in [1, 2, 3, 5]:
        returns = [t[f'return_{hold_days}d'] for t in all_trades if t.get(f'return_{hold_days}d') is not None]
        
        if not returns:
            continue
        
        win_count = sum(1 for r in returns if r > 0)
        lose_count = sum(1 for r in returns if r <= 0)
        win_rate = win_count / len(returns) * 100
        avg_return = np.mean(returns)
        max_return = max(returns)
        max_loss = min(returns)
        median_return = np.median(returns)
        
        line = f"""
┌─ 持有{hold_days}天 ─────────────────────────
│  总交易: {len(returns)} 笔
│  胜率: {win_rate:.1f}% ({win_count}胜 {lose_count}负)
│  平均收益: {avg_return:+.2f}%
│  中位数: {median_return:+.2f}%
│  最大盈利: {max_return:+.2f}%
│  最大亏损: {max_loss:+.2f}%
└─────────────────────────────────"""
        summary_lines.append(line)
        print(line)
    
    # 止盈止损模拟（5%止盈，3%止损，最多持有5天）
    print(f"\n📋 模拟止盈止损（+5%止盈，-3%止损，最多持有5天）")
    
    sim_wins = 0
    sim_losses = 0
    sim_returns = []
    
    for trade in all_trades:
        # 逐天检查是否触发止盈止损
        triggered = False
        for d in range(1, 6):
            ret = trade.get(f'return_{d}d')
            if ret is None:
                continue
            if ret >= 5:  # 止盈
                sim_returns.append(5.0)
                sim_wins += 1
                triggered = True
                break
            elif ret <= -3:  # 止损
                sim_returns.append(-3.0)
                sim_losses += 1
                triggered = True
                break
        
        if not triggered:
            # 持有到最后一天
            final_ret = trade.get('return_5d')
            if final_ret is not None:
                sim_returns.append(final_ret)
                if final_ret > 0:
                    sim_wins += 1
                else:
                    sim_losses += 1
    
    if sim_returns:
        sim_win_rate = sim_wins / len(sim_returns) * 100
        sim_avg = np.mean(sim_returns)
        sim_total = sum(sim_returns)
        
        # 假设每次买1万
        avg_per_trade = sim_avg / 100 * 10000
        
        print(f"  总交易: {len(sim_returns)} 笔")
        print(f"  胜率: {sim_win_rate:.1f}%")
        print(f"  平均每笔: {sim_avg:+.2f}% (约{avg_per_trade:+.0f}元/万)")
        print(f"  累计收益: {sim_total:+.1f}% (如果每次买1万，总盈亏约{sim_total/100*10000:+.0f}元)")
    
    # 按得分分档统计
    print(f"\n📋 按得分分档统计（持有3天收益）")
    for threshold in [50, 60, 70]:
        returns = [t['return_3d'] for t in all_trades 
                   if t.get('return_3d') is not None and t['score'] >= threshold]
        if returns:
            wr = sum(1 for r in returns if r > 0) / len(returns) * 100
            avg = np.mean(returns)
            print(f"  得分≥{threshold}: {len(returns)}笔, 胜率{wr:.1f}%, 平均{avg:+.2f}%")
    
    # 保存详细结果
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    date_str = datetime.now().strftime('%Y%m%d_%H%M')
    path = os.path.join(output_dir, f'backtest_{date_str}.json')
    
    report = {
        'test_days': test_days,
        'score_threshold': score_threshold,
        'total_trades': total_trades,
        'trades': all_trades,
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 详细数据已保存: {path}")
    
    return all_trades


if __name__ == '__main__':
    run_backtest(test_days=20, top_n=50, score_threshold=50)
