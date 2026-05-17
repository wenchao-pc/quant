"""
conftest.py — pytest 全局 fixtures
"""
import sys
import os
import pytest

# 让 quant/ 能被 import，report-generator 也需要
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'report-generator'))

import pandas as pd
import numpy as np


@pytest.fixture
def sample_df():
    """
    标准日K DataFrame，包含120天数据。
    列：日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
    """
    n = 120
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B').astype(str).tolist()
    base = np.random.uniform(10, 50)
    closes = []
    close = base
    for _ in range(n):
        close = close * (1 + np.random.uniform(-0.03, 0.035))
        closes.append(round(close, 2))
    closes = np.array(closes)

    opens = closes * (1 + np.random.uniform(-0.01, 0.01, n))
    highs = np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.02, n))
    lows = np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.02, n))
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = ((closes - prev) / prev * 100).round(2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens.round(2),
        '收盘': closes,
        '最高': highs.round(2),
        '最低': lows.round(2),
        '成交量': np.random.randint(1e6, 1e8, n),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.random.uniform(0.5, 5, n).round(2),
        '涨跌幅': chg_pct,
        '涨跌额': (closes - prev).round(2),
        '换手率': np.random.uniform(0.1, 10, n).round(2),
    })


@pytest.fixture
def golden_cross_df():
    """
    MA5 上穿 MA20 金叉数据。
    前30天平缓，后MA5从下方穿越MA20产生金叉。
    """
    n = 50
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B').astype(str).tolist()
    # 构造趋势：股价从10元涨到25元，MA5从下穿越MA20
    prices = np.linspace(10, 25, n) + np.random.uniform(-0.5, 0.5, n)
    closes = np.round(prices, 2)
    opens = closes * (1 + np.random.uniform(-0.01, 0.01, n))
    highs = np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.015, n))
    lows = np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.015, n))
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = ((closes - prev) / prev * 100).round(2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens.round(2),
        '收盘': closes,
        '最高': highs.round(2),
        '最低': lows.round(2),
        '成交量': np.random.randint(1e6, 1e8, n),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.random.uniform(1, 5, n).round(2),
        '涨跌幅': chg_pct,
        '涨跌额': (closes - prev).round(2),
        '换手率': np.random.uniform(1, 8, n).round(2),
    })


@pytest.fixture
def consecutive_up_df():
    """
    连涨形态数据：最近5天连续上涨。
    """
    n = 30
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B').astype(str).tolist()
    base = 20.0
    # 前25天小幅震荡，后5天每天涨2%
    prices = [base]
    for i in range(1, n - 5):
        prices.append(prices[-1] * (1 + np.random.uniform(-0.015, 0.015)))
    for _ in range(5):
        prices.append(prices[-1] * 1.02)
    closes = np.round(np.array(prices), 2)
    opens = closes * (1 + np.random.uniform(-0.005, 0.005, n))
    highs = np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.01, n))
    lows = np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.01, n))
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = ((closes - prev) / prev * 100).round(2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens.round(2),
        '收盘': closes,
        '最高': highs.round(2),
        '最低': lows.round(2),
        '成交量': np.random.randint(1e6, 1e8, n),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.random.uniform(1, 5, n).round(2),
        '涨跌幅': chg_pct,
        '涨跌额': (closes - prev).round(2),
        '换手率': np.random.uniform(1, 8, n).round(2),
    })


@pytest.fixture
def support_bounce_df():
    """
    MA60支撑反弹数据：价格贴近MA60后反弹。
    """
    n = 80
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B').astype(str).tolist()
    # 股价围绕20元，长期均线在20附近
    base = 20.0
    prices = [base]
    for _ in range(n):
        prices.append(prices[-1] * (1 + np.random.uniform(-0.02, 0.022)))
    closes = np.round(np.array(prices), 2)
    # 让收盘价贴近MA60
    ma60_series = pd.Series(closes).rolling(60).mean()
    closes = np.round(ma60_series.values * (1 + np.random.uniform(-0.02, 0.02, n)), 2)
    closes[-1] = ma60_series.values[-1] * 0.99  # 微跌贴近均线，然后反弹
    opens = closes * (1 + np.random.uniform(-0.01, 0.01, n))
    highs = np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.01, n))
    lows = np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.01, n))
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = ((closes - prev) / prev * 100).round(2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens.round(2),
        '收盘': closes,
        '最高': highs.round(2),
        '最低': lows.round(2),
        '成交量': np.random.randint(1e6, 1e8, n),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.random.uniform(1, 5, n).round(2),
        '涨跌幅': chg_pct,
        '涨跌额': (closes - prev).round(2),
        '换手率': np.random.uniform(0.5, 5, n).round(2),
    })


@pytest.fixture
def volume_price_df():
    """
    量价配合数据：温和放量+上涨。
    """
    n = 30
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n, freq='B').astype(str).tolist()
    base = 15.0
    prices = [base]
    for i in range(1, n):
        if i >= 20:
            prices.append(prices[-1] * 1.015)  # 近期上涨
        else:
            prices.append(prices[-1] * (1 + np.random.uniform(-0.01, 0.01)))
    closes = np.round(np.array(prices), 2)
    # 成交量近5天放大1.8倍
    vols = np.full(n, 5e6)
    vols[-5:] = 9e6
    opens = closes * (1 + np.random.uniform(-0.01, 0.01, n))
    highs = np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.015, n))
    lows = np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.015, n))
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = ((closes - prev) / prev * 100).round(2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens.round(2),
        '收盘': closes,
        '最高': highs.round(2),
        '最低': lows.round(2),
        '成交量': vols.astype(int),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.random.uniform(1, 5, n).round(2),
        '涨跌幅': chg_pct,
        '涨跌额': (closes - prev).round(2),
        '换手率': np.random.uniform(0.5, 8, n).round(2),
    })
