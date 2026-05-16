"""
test_fetcher.py — 数据获取模块单元测试
使用 unittest.mock 直接 patch，避免真实网络请求。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock


def _make_tencent_line(code, name, price, last_close, open_, vol, high, low,
                        price_change, change_pct, turnover):
    """
    构造腾讯行情API格式的mock数据行。
    腾讯API有88个字段，这里构造符合fetcher.py解析逻辑的足够字段。
    关键字段: [1]=name, [2]=code, [3]=price, [4]=last_close, [5]=open,
              [6]=vol, [31]=price_change, [32]=change_pct, [33]=high, [34]=low, [37]=turnover
    """
    prefix = 'sh' if code.startswith(('6', '5')) else 'sz'
    fields = [
        f'v_{prefix}{code.zfill(6)}',  # [0]
        name,        # [1]
        code.zfill(6),  # [2]
        str(price),  # [3]
        str(last_close),  # [4]
        str(open_),  # [5]
        str(vol),    # [6]
        '',          # [7] - [32] empty padding to reach index 33
        str(high),   # [33]
        str(low),    # [34]
        '',          # [35]
        '',          # [36]
        str(turnover),  # [37]
    ]
    # Pad fields[7] to fields[32] with empty strings (26 empty fields)
    result = fields[:8] + [''] * 25 + fields[8:]
    return '~'.join(result) + '~'


class TestFetchTencentBatch:
    """fetch_tencent_batch 解析逻辑测试"""

    def test_parse_valid_response(self):
        """正常腾讯行情响应应正确解析"""
        import data.fetcher as fetcher

        line1 = _make_tencent_line('000001', '平安银行', 45.55, 45.20, 45.30, 1000000,
                                    45.80, 45.10, 0.35, 0.77, 50000000)
        line2 = _make_tencent_line('600000', '浦发银行', 10.20, 10.10, 10.15, 5000000,
                                    10.25, 10.05, 0.10, 0.99, 20000000)
        mock_text = line1 + ';' + line2

        with patch.object(fetcher.requests, 'get') as mock_get:
            mock_response = MagicMock()
            type(mock_response).text = PropertyMock(return_value=mock_text)
            mock_get.return_value = mock_response
            df = fetcher.fetch_tencent_batch(['000001', '600000'])

        assert len(df) == 2
        assert df.iloc[0]['名称'] == '平安银行'
        assert df.iloc[0]['最新价'] == 45.55
        assert df.iloc[1]['代码'] == '600000'

    def test_filter_zero_price(self):
        """价格为0的股票应被过滤"""
        import data.fetcher as fetcher

        # 第一条：price=0（应被过滤）
        line1 = _make_tencent_line('000001', '平安银行', 0.00, 45.20, 45.30, 1000000,
                                    45.80, 45.10, 0, 0, 50000000)
        # 第二条：price=10.20（应保留）
        line2 = _make_tencent_line('600000', '浦发银行', 10.20, 10.10, 10.15, 5000000,
                                    10.25, 10.05, 0.10, 0.99, 20000000)
        mock_text = line1 + ';' + line2

        with patch.object(fetcher.requests, 'get') as mock_get:
            mock_response = MagicMock()
            type(mock_response).text = PropertyMock(return_value=mock_text)
            mock_get.return_value = mock_response
            df = fetcher.fetch_tencent_batch(['000001', '600000'])

        assert len(df) == 1
        assert df.iloc[0]['代码'] == '600000'
        assert df.iloc[0]['名称'] == '浦发银行'

    def test_batch_code_format(self):
        """股票代码应正确补零并拼接前缀"""
        import data.fetcher as fetcher

        codes = ['1', '000001', '600000', '300001']
        with patch.object(fetcher.requests, 'get') as mock_get:
            mock_response = MagicMock()
            type(mock_response).text = PropertyMock(return_value='')
            mock_get.return_value = mock_response
            fetcher.fetch_tencent_batch(codes)

            url = mock_get.call_args[0][0]
            assert 'sh600000' in url, f"期望 sh600000 在 URL 中: {url}"
            assert 'sz000001' in url, f"期望 sz000001 在 URL 中: {url}"
            assert 'sz300001' in url, f"期望 sz300001 在 URL 中: {url}"


class TestGetStockHistory:
    """get_stock_history 缓存逻辑测试"""

    def test_load_cache_returns_dataframe(self, tmp_path):
        """缓存命中时直接返回，不发网络请求"""
        import data.fetcher as fetcher

        cache_dir = tmp_path / 'cache'
        cache_dir.mkdir()
        cache_file = cache_dir / 'hist_000001.csv'
        df_cache = pd.DataFrame({
            '日期': [f'2024-01-{i:02d}' for i in range(1, 26)],
            '开盘': [10.0] * 25,
            '收盘': [10.5] * 25,
            '最高': [11.0] * 25,
            '最低': [9.5] * 25,
            '成交量': [1000000] * 25,
            '成交额': [0] * 25,
            '振幅': [0] * 25,
            '涨跌幅': [0.0] * 25,
            '涨跌额': [0.0] * 25,
            '换手率': [0] * 25,
        })
        df_cache.to_csv(cache_file, index=False)

        with patch.object(fetcher, 'CACHE_DIR', str(cache_dir)):
            with patch.object(fetcher.requests, 'get') as mock_get:
                result = fetcher.get_stock_history('000001')

        assert len(result) == 25
        mock_get.assert_not_called()

    def test_cache_stale_triggers_fetch(self, tmp_path):
        """缓存过期时应发起网络请求（baostock返回空，sina降级返回空）"""
        import data.fetcher as fetcher

        cache_dir = tmp_path / 'cache'
        cache_dir.mkdir()
        cache_file = cache_dir / 'hist_000001.csv'
        df_old = pd.DataFrame({
            '日期': ['2024-01-01'],
            '开盘': [10.0], '收盘': [10.0],
            '最高': [10.0], '最低': [10.0], '成交量': [1000000],
            '成交额': [0], '振幅': [0], '涨跌幅': [0],
            '涨跌额': [0], '换手率': [0],
        })
        df_old.to_csv(cache_file, index=False)
        old_mtime = 1000000000.0
        os.utime(cache_file, (old_mtime, old_mtime))

        with patch.object(fetcher, 'CACHE_DIR', str(cache_dir)):
            with patch.dict('sys.modules', {'baostock': MagicMock()}):
                with patch.object(fetcher.requests, 'get') as mock_get:
                    mock_response = MagicMock()
                    type(mock_response).text = PropertyMock(return_value='[]')
                    type(mock_response).status_code = PropertyMock(return_value=200)
                    mock_get.return_value = mock_response
                    result = fetcher.get_stock_history('000001')

        # 两级API都失败，最终返回空DataFrame
        assert len(result) == 0
        mock_get.assert_called()


class TestGenerateStockCodes:
    """_generate_stock_codes 边界测试"""

    def test_code_ranges(self):
        """生成的代码范围应覆盖沪市、深市、创业板、科创板"""
        from data.fetcher import _generate_stock_codes
        codes = _generate_stock_codes()
        codes_str = [str(c) for c in codes]

        assert any(c.startswith('600') for c in codes_str), "缺少沪市主板"
        assert any(c.startswith('000') for c in codes_str), "缺少深市主板"
        assert any(c.startswith('300') for c in codes_str), "缺少创业板"
        assert any(c.startswith('688') for c in codes_str), "缺少科创板"
        assert len(codes) > 4000
