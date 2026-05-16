"""
test_backtest.py — 回测模块单元测试
测试 analyze_stock_at_date 核心逻辑（backtest.py 0% 覆盖 → 有覆盖）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch


def _dates(n, start='2026-01-01'):
    base = pd.Timestamp(start)
    return [(base + pd.Timedelta(days=i * 2)).strftime('%Y-%m-%d') for i in range(n)]


def make_df(n=70, base_price=20.0):
    """构造标准测试用 DataFrame，70天数据"""
    dates = _dates(n)
    raw = [base_price]
    for _ in range(n - 1):
        raw.append(raw[-1] * (1 + np.random.uniform(-0.02, 0.022)))
    closes = np.round(np.array(raw), 2)
    opens = np.round(closes * (1 + np.random.uniform(-0.005, 0.005, n)), 2)
    highs = np.round(np.maximum(opens, closes) * (1 + np.random.uniform(0, 0.01, n)), 2)
    lows = np.round(np.minimum(opens, closes) * (1 - np.random.uniform(0, 0.01, n)), 2)
    prev = np.roll(closes, 1)
    prev[0] = closes[0]
    chg_pct = np.round((closes - prev) / prev * 100, 2)

    return pd.DataFrame({
        '日期': dates,
        '开盘': opens,
        '收盘': closes,
        '最高': highs,
        '最低': lows,
        '成交量': np.random.randint(1e6, 1e8, n),
        '成交额': np.random.randint(1e7, 1e9, n),
        '振幅': np.round(np.random.uniform(0.5, 4, n), 2),
        '涨跌幅': chg_pct,
        '涨跌额': np.round(closes - prev, 2),
        '换手率': np.round(np.random.uniform(0.5, 8, n), 2),
    })


class TestAnalyzeStockAtDate:
    """analyze_stock_at_date() 评分计算测试"""

    def test_insufficient_data_returns_none(self):
        """数据不足30天返回 None"""
        import backtest
        df = make_df(n=20)  # 少于30天
        result = backtest.analyze_stock_at_date(df, end_idx=19)
        assert result is None

    def test_score_is_weighted_average(self):
        """返回值是4个策略的加权平均（0-100范围内）"""
        import backtest
        # 全部用同一份数据，各策略都有明确信号
        df = make_df(n=70)

        # Mock 各策略返回固定高分
        with patch.object(backtest, 'strategy_ma_breakthrough', return_value=(80, {})):
            with patch.object(backtest, 'strategy_volume_price', return_value=(60, {})):
                with patch.object(backtest, 'strategy_consecutive_up', return_value=(70, {})):
                    with patch.object(backtest, 'strategy_support_bounce', return_value=(50, {})):
                        score = backtest.analyze_stock_at_date(df, end_idx=69)

        assert score is not None
        assert 0 <= score <= 100
        # 验证加权计算: 0.3*80 + 0.3*60 + 0.25*70 + 0.15*50 = 24+18+17.5+7.5 = 67
        expected = 0.3 * 80 + 0.3 * 60 + 0.25 * 70 + 0.15 * 50
        assert abs(score - expected) < 0.5

    def test_zero_score_strategies_returns_zero(self):
        """所有策略得0分时，总分应为0"""
        import backtest
        df = make_df(n=70)

        with patch.object(backtest, 'strategy_ma_breakthrough', return_value=(0, {})):
            with patch.object(backtest, 'strategy_volume_price', return_value=(0, {})):
                with patch.object(backtest, 'strategy_consecutive_up', return_value=(0, {})):
                    with patch.object(backtest, 'strategy_support_bounce', return_value=(0, {})):
                        score = backtest.analyze_stock_at_date(df, end_idx=69)

        assert score == 0

    def test_all_strategies_return_valid_scores(self):
        """各策略返回固定分时，总分为加权平均"""
        import backtest
        df = make_df(n=70)

        # Mock 各策略返回固定高分
        with patch.object(backtest, 'strategy_ma_breakthrough', return_value=(80, {})):
            with patch.object(backtest, 'strategy_volume_price', return_value=(60, {})):
                with patch.object(backtest, 'strategy_consecutive_up', return_value=(70, {})):
                    with patch.object(backtest, 'strategy_support_bounce', return_value=(50, {})):
                        score = backtest.analyze_stock_at_date(df, end_idx=69)

        assert score is not None
        assert 0 <= score <= 100
        # 验证加权计算: 0.3*80 + 0.3*60 + 0.25*70 + 0.15*50 = 24+18+17.5+7.5 = 67
        expected = 0.3 * 80 + 0.3 * 60 + 0.25 * 70 + 0.15 * 50
        assert abs(score - expected) < 0.5

    def test_end_idx_truncates_data(self):
        """end_idx 截断数据，只用截断前的数据跑策略"""
        import backtest
        df = make_df(n=70)

        # 记录传给策略的数据长度，验证确实被截断了
        captured_lengths = []

        def mock_strat(df_cut):
            captured_lengths.append(len(df_cut))
            return 50, {}

        with patch.object(backtest, 'strategy_ma_breakthrough', side_effect=mock_strat):
            with patch.object(backtest, 'strategy_volume_price', side_effect=mock_strat):
                with patch.object(backtest, 'strategy_consecutive_up', side_effect=mock_strat):
                    with patch.object(backtest, 'strategy_support_bounce', side_effect=mock_strat):
                        backtest.analyze_stock_at_date(df, end_idx=49)  # 只取前50天

        # 所有策略收到的数据长度都应该是 50（end_idx+1）
        assert all(length == 50 for length in captured_lengths)


class TestBacktestEdgeCases:
    """回测边界情况测试"""

    def test_analyze_stock_at_date_at_last_index(self):
        """用最后一天作为 end_idx（回测起点）"""
        import backtest
        df = make_df(n=70)

        with patch.object(backtest, 'strategy_ma_breakthrough', return_value=(75, {})):
            with patch.object(backtest, 'strategy_volume_price', return_value=(75, {})):
                with patch.object(backtest, 'strategy_consecutive_up', return_value=(75, {})):
                    with patch.object(backtest, 'strategy_support_bounce', return_value=(75, {})):
                        score = backtest.analyze_stock_at_date(df, end_idx=len(df) - 1)

        # 75 * (0.3+0.3+0.25+0.15) = 75
        assert score == 75

    def test_score_rounded_to_one_decimal(self):
        """得分保留1位小数"""
        import backtest
        df = make_df(n=70)

        with patch.object(backtest, 'strategy_ma_breakthrough', return_value=(33, {})):
            with patch.object(backtest, 'strategy_volume_price', return_value=(33, {})):
                with patch.object(backtest, 'strategy_consecutive_up', return_value=(33, {})):
                    with patch.object(backtest, 'strategy_support_bounce', return_value=(33, {})):
                        score = backtest.analyze_stock_at_date(df, end_idx=69)

        # 检查是否为1位小数
        assert round(score, 1) == score