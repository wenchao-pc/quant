"""
test_generate.py — 报告生成模块单元测试
测试：is_trading_day, get_trading_days_count, update_trading, save_json

patch 策略：
- akshare/requests 在函数内部 import，需 patch sys.modules 中对应的模块对象，
  而不是 patch.object(gen, 'xxx')（因为 gen 是模块，函数内局部 import 不属于模块属性）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import importlib
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


def reload_gen():
    """重新导入 report-generator.generate（清除旧模块缓存）"""
    mods = [k for k in list(sys.modules.keys()) if k.startswith('report')]
    for m in mods:
        del sys.modules[m]
    return importlib.import_module('report-generator.generate')


class TestIsTradingDay:
    """is_trading_day() 交易日判断测试"""

    def test_saturday_returns_false(self):
        """周六（非交易日）返回 False"""
        gen = reload_gen()
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2026, 5, 9)  # 2026-05-09 是周六
        mock_dt.weekday.return_value = 5

        with patch.object(gen, 'datetime', mock_dt):
            result = gen.is_trading_day()
        assert result is False

    def test_sunday_returns_false(self):
        """周日（非交易日）返回 False"""
        gen = reload_gen()
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2026, 5, 10)  # 周日
        mock_dt.weekday.return_value = 6

        with patch.object(gen, 'datetime', mock_dt):
            result = gen.is_trading_day()
        assert result is False

    def test_weekday_trading_day_returns_true(self):
        """工作日且 akshare 确认是交易日时返回 True"""
        gen = reload_gen()
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2026, 5, 11)  # 周一
        mock_dt.weekday.return_value = 0

        mock_df = MagicMock()
        col_series = MagicMock()
        col_series.astype.return_value.tolist.return_value = ['2026-05-11']
        mock_df.__getitem__.side_effect = lambda key: col_series
        mock_ak = MagicMock()
        mock_ak.tool_trade_date_hist_sina.return_value = mock_df

        with patch.object(gen, 'datetime', mock_dt):
            with patch.dict('sys.modules', {'akshare': mock_ak}):
                result = gen.is_trading_day()
        assert result is True

    def test_weekday_not_in_trading_calendar_returns_false(self):
        """工作日但不在交易日历中（如节假日）返回 False"""
        import baostock as real_bs
        gen = reload_gen()
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2026, 5, 11)  # 周一
        mock_dt.weekday.return_value = 0

        with patch.object(gen, 'datetime', mock_dt):
            with patch.object(real_bs, 'query_trade_dates') as mock_qtd:
                # baostock 返回今天不在交易日历中（非交易日）
                mock_rs = MagicMock()
                mock_rs.error_code = '0'
                mock_rs.next = MagicMock(return_value=False)  # 无数据返回
                mock_qtd.return_value = mock_rs
                with patch.object(real_bs, 'login', return_value=mock_rs):
                    with patch.object(real_bs, 'logout', return_value=None):
                        result = gen.is_trading_day()
        assert result is False


class TestGetTradingDaysCount:
    """get_trading_days_count() 计算两个交易日之间的交易日数量"""

    def test_same_day_returns_zero(self):
        """同一天返回0"""
        gen = reload_gen()
        mock_df = MagicMock()
        col_series = MagicMock()
        col_series.astype.return_value.tolist.return_value = ['2026-05-06', '2026-05-07', '2026-05-08']
        mock_df.__getitem__.side_effect = lambda key: col_series
        mock_ak = MagicMock()
        mock_ak.tool_trade_date_hist_sina.return_value = mock_df

        with patch.dict('sys.modules', {'akshare': mock_ak}):
            result = gen.get_trading_days_count('2026-05-06', '2026-05-06')
        assert result == 0

    def test_one_trading_day_between(self):
        """相邻两个交易日间隔1"""
        gen = reload_gen()
        mock_df = MagicMock()
        col_series = MagicMock()
        col_series.astype.return_value.tolist.return_value = ['2026-05-06', '2026-05-07', '2026-05-08']
        mock_df.__getitem__.side_effect = lambda key: col_series
        mock_ak = MagicMock()
        mock_ak.tool_trade_date_hist_sina.return_value = mock_df

        with patch.dict('sys.modules', {'akshare': mock_ak}):
            result = gen.get_trading_days_count('2026-05-06', '2026-05-07')
        assert result == 1

    def test_skips_weekend(self):
        """跨周末时正确计算（周一到上周五=3天）"""
        import baostock as real_bs
        gen = reload_gen()

        with patch.object(real_bs, 'query_trade_dates') as mock_qtd:
            mock_rs = MagicMock()
            mock_rs.error_code = '0'
            mock_rs.next = MagicMock(side_effect=[True, True, True, True, False])
            mock_rs.get_row_data = MagicMock(side_effect=[
                ['2026-05-06', '1'], ['2026-05-07', '1'],
                ['2026-05-08', '1'], ['2026-05-09', '1'],
            ])
            mock_qtd.return_value = mock_rs
            with patch.object(real_bs, 'login', return_value=mock_rs):
                with patch.object(real_bs, 'logout', return_value=None):
                    result = gen.get_trading_days_count('2026-05-06', '2026-05-09')
        assert result == 3  # 5/6被排除，5/7,5/8,5/9共3个交易日

    def test_multiple_days_between(self):
        """间隔多个交易日"""
        import baostock as real_bs
        gen = reload_gen()

        with patch.object(real_bs, 'query_trade_dates') as mock_qtd:
            mock_rs = MagicMock()
            mock_rs.error_code = '0'
            mock_rs.next = MagicMock(side_effect=[True, True, True, True, True, False])
            mock_rs.get_row_data = MagicMock(side_effect=[
                ['2026-05-06', '1'], ['2026-05-07', '1'],
                ['2026-05-08', '1'], ['2026-05-09', '1'],
                ['2026-05-11', '1'],
            ])
            mock_qtd.return_value = mock_rs
            with patch.object(real_bs, 'login', return_value=mock_rs):
                with patch.object(real_bs, 'logout', return_value=None):
                    result = gen.get_trading_days_count('2026-05-06', '2026-05-11')
        assert result == 4  # 5/6被排除，5/7,5/8,5/9,5/11共4个交易日


class TestUpdateTracking:
    """update_trading() 持仓追踪去重测试"""

    def test_duplicate_same_day_same_code_skipped(self, tmp_path):
        """
        同一天对同一只股票发两次信号，只应添加一次。
        修复前 bug：只检查 entry_date==today，未检查 code 是否已在 active 中。
        """
        tracking_path = tmp_path / 'data' / 'tracking.json'
        tracking_path.parent.mkdir(exist_ok=True)
        tracking_path.write_text(json.dumps({
            'active': [
                {'code': '000001', 'name': '平安银行', 'entry_date': '2026-05-08',
                 'entry_price': 10.0, 'entry_score': 75, 'current_price': 10.0,
                 'current_return': 0, 'status': 'holding', 'days': 0}
            ],
            'closed': [],
            'summary': {'total_signals': 1, 'wins': 0, 'total_return': 0}
        }))

        data = {
            'date': '2026-05-08',
            'signals': [
                {'code': '000001', 'name': '平安银行', 'price': 10.2, 'total_score': 80}
            ]
        }

        gen = reload_gen()
        orig_report_dir = gen.REPORT_DIR
        gen.REPORT_DIR = str(tmp_path)

        try:
            with patch.dict('sys.modules', {'requests': MagicMock()}):
                try:
                    gen.update_trading(data)
                except Exception:
                    pass

            result = json.loads(tracking_path.read_text())
            active_count = sum(1 for p in result['active'] if p['code'] == '000001')
            assert active_count == 1, f"去重失败，active中出现了{active_count}次000001"
        finally:
            gen.REPORT_DIR = orig_report_dir

    def test_new_stock_added(self, tmp_path):
        """新股票正确添加进 active"""
        tracking_path = tmp_path / 'data' / 'tracking.json'
        tracking_path.parent.mkdir(exist_ok=True)
        tracking_path.write_text(json.dumps({
            'active': [],
            'closed': [],
            'summary': {'total_signals': 0, 'wins': 0, 'total_return': 0}
        }))

        data = {
            'date': '2026-05-08',
            'signals': [
                {'code': '600000', 'name': '浦发银行', 'price': 10.0, 'total_score': 80}
            ]
        }

        gen = reload_gen()
        orig_report_dir = gen.REPORT_DIR
        gen.REPORT_DIR = str(tmp_path)

        try:
            with patch.dict('sys.modules', {'requests': MagicMock()}):
                try:
                    gen.update_trading(data)
                except Exception:
                    pass

            result = json.loads(tracking_path.read_text())
            assert len(result['active']) == 1
            assert result['active'][0]['code'] == '600000'
            assert result['summary']['total_signals'] == 1
        finally:
            gen.REPORT_DIR = orig_report_dir


class TestSaveJson:
    """save_json() 输出测试"""

    def test_json_file_created(self, tmp_path):
        """JSON 文件正确生成"""
        quant_dir = tmp_path / 'quant'
        quant_dir.mkdir()
        report_dir = tmp_path / 'quant-report'
        report_dir.mkdir()

        data = {
            'date': '2026-05-08',
            'weekday': '周四',
            'generated_at': '2026-05-08 15:30:00',
            'total_scanned': 3000,
            'active_analyzed': 80,
            'signal_count': 3,
            'market': {},
            'signals': [],
            'top10': [],
            'backtest': {},
        }

        gen = reload_gen()
        orig_base = gen.BASE_DIR
        orig_report = gen.REPORT_DIR
        orig_quant = gen.QUANT_DIR

        gen.BASE_DIR = str(quant_dir)
        gen.REPORT_DIR = str(report_dir)
        gen.QUANT_DIR = str(quant_dir)

        try:
            gen.save_json(data)
            json_file = report_dir / 'reports' / '2026-05-08' / 'data.json'
            assert json_file.exists()
            loaded = json.loads(json_file.read_text())
            assert loaded['date'] == '2026-05-08'
            assert loaded['signal_count'] == 3
        finally:
            gen.BASE_DIR = orig_base
            gen.REPORT_DIR = orig_report
            gen.QUANT_DIR = orig_quant
