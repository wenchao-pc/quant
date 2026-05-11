"""
test_strategies.py — 策略函数单元测试
覆盖 main.py 中所有 4 个因子评分函数。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np

from main import (
    calc_ma,
    strategy_ma_breakthrough,
    strategy_volume_price,
    strategy_consecutive_up,
    strategy_support_bounce,
)


# =============================================================================
# 工具：构造测试用 DataFrame
# =============================================================================

def _dates(n):
    """生成 n 个形如 '2026-MM-DD' 的日期字符串（每隔2天，无周末问题）"""
    base = pd.Timestamp('2026-01-01')
    return [(base + pd.Timedelta(days=i * 2)).strftime('%Y-%m-%d') for i in range(n)]


def make_consec_df(consecutive_up_days, n_total=30, base_price=20.0):
    """
    构造连续上涨的 DataFrame。
    consecutive_up_days: 最后几天连续涨（每天涨2%）
    """
    n = n_total
    dates = _dates(n)
    # 全部横盘（pct_change ≈ 0，消除误判）
    raw = [float(base_price)] * n
    # 末尾添加 consecutive_up_days 天，每天涨 2%
    start = raw[-1]
    for i in range(consecutive_up_days):
        raw.append(round(start * (1.02 ** (i + 1)), 2))
    dates = _dates(len(raw))

    n_final = len(raw)
    closes = [round(float(p), 2) for p in raw]
    prev_close = [closes[0]] + closes[:-1]
    chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
    chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

    return pd.DataFrame({
        '日期': dates,
        '开盘': closes,
        '收盘': closes,
        '最高': [round(c * 1.005, 2) for c in closes],
        '最低': [round(c * 0.995, 2) for c in closes],
        '成交量': [5_000_000] * n_final,
        '成交额': [100_000_000] * n_final,
        '振幅': [1.0] * n_final,
        '涨跌幅': chg_pct,
        '涨跌额': chg_amt,
        '换手率': [1.0] * n_final,
    })


def make_golden_cross_df():
    """
    构造 MA5 上穿 MA20 金叉数据。
    - 倒数第2天: MA5 < MA20
    - 倒数第1天: MA5 > MA20（当天产生金叉）
    """
    n = 50
    dates = _dates(n)

    raw = [20.0] * n
    raw[-4] = 17.5
    raw[-3] = 15.25
    raw[-2] = 17.5
    raw[-1] = 30.0

    closes = [round(float(p), 2) for p in raw]
    prev_close = [closes[0]] + closes[:-1]
    chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
    chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

    return pd.DataFrame({
        '日期': dates,
        '开盘': closes,
        '收盘': closes,
        '最高': [round(c * 1.005, 2) for c in closes],
        '最低': [round(c * 0.995, 2) for c in closes],
        '成交量': [5_000_000] * n,
        '成交额': [100_000_000] * n,
        '振幅': [1.0] * n,
        '涨跌幅': chg_pct,
        '涨跌额': chg_amt,
        '换手率': [1.0] * n,
    })


def make_bearish_df():
    """空头排列：MA5 < MA20，股价在 MA5 下方。"""
    n = 50
    dates = _dates(n)
    base_prices = np.linspace(30, 10, n)
    closes = [round(float(p + np.random.uniform(-0.2, 0.2)), 2) for p in base_prices]
    prev_close = [closes[0]] + closes[:-1]
    chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
    chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

    return pd.DataFrame({
        '日期': dates,
        '开盘': closes,
        '收盘': closes,
        '最高': [round(c * 1.005, 2) for c in closes],
        '最低': [round(c * 0.995, 2) for c in closes],
        '成交量': [5_000_000] * n,
        '成交额': [100_000_000] * n,
        '振幅': [1.0] * n,
        '涨跌幅': chg_pct,
        '涨跌额': chg_amt,
        '换手率': [1.0] * n,
    })


def make_support_bounce_df():
    """
    MA60 支撑反弹：
    - 数据量 >= 65
    - 最新收盘贴近 MA60（偏离 -3%~+2%）
    - 当天收涨
    """
    n = 80
    dates = _dates(n)

    rng = np.random.default_rng(123)
    base = 20.0
    prices = [base]
    for i in range(1, n):
        prices.append(prices[-1] * (1 + rng.uniform(0.0, 0.025)))

    closes_for_ma = [float(p) for p in prices[:-1]]
    ma60_vals = pd.Series(closes_for_ma).rolling(60).mean().values.tolist()

    # 倒数第2天贴近 MA60 形成支撑
    prices[-2] = round(float(ma60_vals[-1]) * 0.990, 2)
    # 最新收盘：贴近 MA60 且相对于前一天上涨（反弹）
    prices[-1] = round(float(ma60_vals[-1]) * 0.990 * 1.010, 2)

    closes = [round(float(p), 2) for p in prices]
    prev_close = [closes[0]] + closes[:-1]
    chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
    chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

    return pd.DataFrame({
        '日期': dates,
        '开盘': closes,
        '收盘': closes,
        '最高': [round(c * 1.005, 2) for c in closes],
        '最低': [round(c * 0.995, 2) for c in closes],
        '成交量': [5_000_000] * n,
        '成交额': [100_000_000] * n,
        '振幅': [1.0] * n,
        '涨跌幅': chg_pct,
        '涨跌额': chg_amt,
        '换手率': [1.0] * n,
    })


def make_volume_price_df():
    """量价配合：近5天成交量放大1.8倍 + 价格上涨。"""
    n = 30
    dates = _dates(n)

    base = 15.0
    prices = [base]
    for i in range(1, n):
        if i >= 20:
            prices.append(prices[-1] * 1.015)
        else:
            prices.append(prices[-1] * (1 + np.random.uniform(-0.01, 0.01)))

    closes = [round(float(p), 2) for p in prices]
    vols = [5_000_000] * n
    for i in range(n - 5, n):
        vols[i] = 9_000_000
    prev_close = [closes[0]] + closes[:-1]
    chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
    chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

    return pd.DataFrame({
        '日期': dates,
        '开盘': closes,
        '收盘': closes,
        '最高': [round(c * 1.005, 2) for c in closes],
        '最低': [round(c * 0.995, 2) for c in closes],
        '成交量': vols,
        '成交额': [100_000_000] * n,
        '振幅': [1.0] * n,
        '涨跌幅': chg_pct,
        '涨跌额': chg_amt,
        '换手率': [1.0] * n,
    })


# =============================================================================
# 测试 calc_ma
# =============================================================================
class TestCalcMA:
    def test_ma_basic(self):
        s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        ma3 = calc_ma(s, 3)
        assert ma3.iloc[-1] == 40.0

    def test_ma_short_series(self):
        s = pd.Series([10.0, 20.0])
        ma3 = calc_ma(s, 3)
        assert pd.isna(ma3.iloc[-1])


# =============================================================================
# 测试 strategy_ma_breakthrough
# =============================================================================
class TestMABreakthrough:
    def test_golden_cross_score(self):
        """金叉：MA5上穿MA20，得分应 >= 80"""
        df = make_golden_cross_df()
        score, info = strategy_ma_breakthrough(df)
        assert score >= 80, f"金叉得分过低: {score}, info={info}"

    def test_golden_cross_signal(self):
        """金叉信号包含 MA5、MA20 关键词"""
        df = make_golden_cross_df()
        _, info = strategy_ma_breakthrough(df)
        signal = info.get('signal', '')
        assert 'MA5' in signal and 'MA20' in signal

    def test_bearish_returns_zero(self):
        """空头排列得分应为0"""
        df = make_bearish_df()
        score, info = strategy_ma_breakthrough(df)
        assert score == 0
        assert '空头' in info.get('signal', '')

    def test_short_data_returns_zero(self):
        """数据不足30天返回0"""
        df = make_consec_df(3, n_total=20)
        score, _ = strategy_ma_breakthrough(df)
        assert score == 0


# =============================================================================
# 测试 strategy_volume_price
# =============================================================================
class TestVolumePrice:
    def test_high_volume_rising(self):
        """放量上涨应得高分（>= 50）"""
        df = make_volume_price_df()
        score, info = strategy_volume_price(df)
        assert score >= 50, f"放量上涨得分过低: {score}, {info}"

    def test_normal_volume_returns_zero(self):
        """成交量恒定、无异常时得0分"""
        n = 30
        dates = _dates(n)
        closes = [round(p, 2) for p in np.linspace(10, 15, n)]
        prev_close = [closes[0]] + closes[:-1]
        chg_pct = [round((c - p) / p * 100, 2) for c, p in zip(closes, prev_close)]
        chg_amt = [round(c - p, 2) for c, p in zip(closes, prev_close)]

        df = pd.DataFrame({
            '日期': dates,
            '开盘': closes,
            '收盘': closes,
            '最高': closes,
            '最低': closes,
            '成交量': [5_000_000] * n,
            '成交额': [100_000_000] * n,
            '振幅': [1.0] * n,
            '涨跌幅': chg_pct,
            '涨跌额': chg_amt,
            '换手率': [1.0] * n,
        })
        score, _ = strategy_volume_price(df)
        assert score == 0

    def test_short_data_returns_zero(self):
        """数据不足10天返回0"""
        df = make_consec_df(3, n_total=5)
        score, _ = strategy_volume_price(df)
        assert score == 0


# =============================================================================
# 测试 strategy_consecutive_up（重点测试评分覆盖 bug）
# =============================================================================
class TestConsecutiveUp:
    def test_2_consecutive_days(self):
        """连涨2天得40分"""
        df = make_consec_df(2)
        score, _ = strategy_consecutive_up(df)
        assert score == 40, f"连涨2天得分为{score}，期望40"

    def test_3_consecutive_days(self):
        """连涨3天得70分"""
        df = make_consec_df(3)
        score, _ = strategy_consecutive_up(df)
        assert score == 70, f"连涨3天得分为{score}，期望70"

    def test_4_consecutive_days(self):
        """连涨4天得90分（强势）"""
        df = make_consec_df(4)
        score, info = strategy_consecutive_up(df)
        assert score == 90, f"连涨4天得分为{score}，期望90"
        assert '强势' in info.get('signal', '')

    def test_5_consecutive_days_no_overwrite(self):
        """
        连涨5天得50分（注意回调），不是90分。
        修复前 bug：先命中 consec>=4 得90，又被 consec>=5 覆盖成50。
        修复后直接命中 consec>=5，得50。
        """
        df = make_consec_df(5)
        score, info = strategy_consecutive_up(df)
        assert score == 50, f"连涨5天bug：得分为{score}，期望50（注意回调）"
        assert '注意回调' in info.get('signal', '')

    def test_6_consecutive_days(self):
        """连涨6天也得50分（注意回调）"""
        df = make_consec_df(6)
        score, info = strategy_consecutive_up(df)
        assert score == 50, f"连涨6天得分为{score}，期望50"
        assert '注意回调' in info.get('signal', '')

    def test_short_data_returns_zero(self):
        """数据不足5天返回0"""
        df = make_consec_df(1, n_total=3)
        score, _ = strategy_consecutive_up(df)
        assert score == 0


# =============================================================================
# 测试 strategy_support_bounce
# =============================================================================
class TestSupportBounce:
    def test_near_ma60_bounce(self):
        """贴近MA60反弹应得 >= 50分"""
        df = make_support_bounce_df()
        score, info = strategy_support_bounce(df)
        assert score >= 50, f"支撑反弹得分过低: {score}, {info}"

    def test_short_data_returns_zero(self):
        """数据不足65天返回0"""
        df = make_consec_df(3, n_total=30)
        score, _ = strategy_support_bounce(df)
        assert score == 0
