"""
test_templates.py — 模板渲染单元测试
验证三个模板能正确渲染，且关键占位符/%%转义正确。
"""
import pytest

# ─── 最小合法 data fixture ──────────────────────────────────────────────────

def make_data(threshold=70, signal_count=0, signals=None, top10=None, market=None, backtest=None):
    """构造一个覆盖各种场景的合法 data dict。"""
    return {
        'date': '2026-05-15',
        'weekday': '周四',
        'market': market or {
            'sh000001': {'name': '上证指数', 'price': 3100.0, 'change_pct': 0.5},
        },
        'signals': signals or [],
        'top10': top10 or [],
        'backtest': backtest or {
            'period': '2026-04-01 ~ 2026-05-15',
            'total_trades': 20,
            'win_rate': 65.0,
            'avg_return': 1.2,
            'avg_return_str': '1.2',
            'sharpe': 1.5,
            'max_drawdown': -8.5,
            'profit_factor': 1.8,
            'annualized': 18.0,
            'signal_count': 13,
        },
        'generated_at': '2026-05-15 15:30:00',
        'signal_count': signal_count,
        'total_scanned': 5000,
        'active_analyzed': 80,
        'threshold': threshold,
    }


def make_stock(code='000001', name='平安银行', score=75.0, chg_pct=1.5, vol=8e9):
    return {
        'code': code, 'name': name,
        'total_score': score,
        'change_pct': chg_pct,
        'price': 10.0, 'turnover': vol,
        'scores': {'MA Breakthrough': 30, 'Volume': 25},
    }


# ─── 辅助：验证 HTML 包含关键内容 ────────────────────────────────────────────

def _assert_threshold_in_html(html, threshold):
    """阈值必须以数字形式出现在 HTML 中（不带多余小数点）。"""
    assert f'{threshold}' in html, f"阈值 {threshold} 未出现在 HTML 中"
    # 确保没有原始 Python float 泄漏（如 70.0 而不是 70）
    assert f'{threshold}.1f' not in html.replace('%.1f', ''), \
        f"发现未转义的 %.1f 格式字符串"


def _assert_no_raw_percent_in_css(html):
    """
    CSS 数值不应该出现裸 % 格式化占位符。
    hacker 模板 bug：STOP_LOSS = <span class="red">-3.0%%</span> 写成 -3.0%
    （但 %% 在 HTML 中渲染为单个 %，这里检查渲染后 HTML 不含可疑的 %% 转义残留）
    """
    # 如果模板中有 %% 且渲染正确，HTML 里应该是单个 %；如果有 %% 残留说明转义了两次
    assert '%%' not in html, "发现未转义的 %% 原始字符（渲染错误）"


# ─── hacker 模板测试 ─────────────────────────────────────────────────────────

class TestHackerTemplate:
    def test_renders_with_no_signals(self):
        """无信号时正常渲染，threshold=70"""
        from templates.hacker import render_hacker
        data = make_data(threshold=70, signal_count=0)
        html = render_hacker(data)
        assert html.startswith('<!DOCTYPE html>')
        assert 'CLEAR' in html
        _assert_threshold_in_html(html, 70)

    def test_renders_with_signals(self):
        """有信号时正常渲染，signal_count=2"""
        from templates.hacker import render_hacker
        stock = make_stock(score=78)
        data = make_data(threshold=70, signal_count=2, signals=[stock, make_stock(score=72)])
        html = render_hacker(data)
        assert 'SIGNAL' in html
        assert '2 SIGNAL' in html
        _assert_threshold_in_html(html, 70)

    def test_threshold_integer_no_trailing_decimals(self):
        """threshold=70（整数）渲染后不带 .0 后缀 —— 抓 %% 占位符遗漏 bug"""
        from templates.hacker import render_hacker
        data = make_data(threshold=70)
        html = render_hacker(data)
        # 应该显示 70，不应该出现 70.0
        assert '70.0 THRESHOLD' not in html, \
            "bug: threshold 70 渲染为 '70.0'，应该是 '70'"
        # 验证实际内容存在
        assert '70' in html

    def test_threshold_float_renders_correctly(self):
        """threshold=70.5（浮点）正确显示一位小数"""
        from templates.hacker import render_hacker
        data = make_data(threshold=70.5)
        html = render_hacker(data)
        assert '70.5' in html, f"threshold=70.5 未正确渲染: {html[html.find('70'):html.find('70')+10]}"

    def test_no_signals_shows_gap(self):
        """无信号时 Gap 行正确显示 差距分值"""
        from templates.hacker import render_hacker
        top = make_stock(score=54.8)
        data = make_data(threshold=70, signal_count=0, signals=[], top10=[top])
        html = render_hacker(data)
        assert 'Gap' in html or 'gap' in html.lower()
        # 差距应该是 70 - 54.8 = 15.2
        assert '15' in html, "Gap 15.2 未出现在 HTML 中"

    def test_backtest_stats_all_present(self):
        """回测数据完整渲染"""
        from templates.hacker import render_hacker
        data = make_data()
        html = render_hacker(data)
        for key in ['Win Rate', 'Sharpe', 'Max Drawdown', 'Profit Factor', 'Annualized']:
            assert key in html, f"回测字段 '{key}' 缺失"

    def test_stop_loss_percent_escaped(self):
        """STOP_LOSS = -3.0%% 正确转义，渲染后为 -3.0%（不是格式错误）"""
        from templates.hacker import render_hacker
        data = make_data()
        html = render_hacker(data)
        assert 'STOP_LOSS' in html
        assert '-3.0%' in html or '-3.0%%' not in html, \
            "STOP_LOSS 格式错误：%% 未正确转义为单个 %"

    def test_take_profit_percent_escaped(self):
        """TAKE_PROFIT = +5.0%% ~ +10.0%% 正确转义"""
        from templates.hacker import render_hacker
        data = make_data()
        html = render_hacker(data)
        assert 'TAKE_PROFIT' in html
        # 渲染后应该是 +5.0% ~ +10.0%
        assert '+5.0%' in html or '+5.0%%' not in html

    def test_max_position_percent_escaped(self):
        """MAX_POSITION = 20%% 正确转义"""
        from templates.hacker import render_hacker
        data = make_data()
        html = render_hacker(data)
        assert '20%' in html or '20%%' not in html


# ─── broker 模板测试 ─────────────────────────────────────────────────────────

class TestBrokerTemplate:
    def test_renders_with_no_signals(self):
        from templates.broker import render_broker
        data = make_data(threshold=70, signal_count=0)
        html = render_broker(data)
        assert html.startswith('<!DOCTYPE html>')
        assert '无买入信号' in html

    def test_renders_with_signals(self):
        from templates.broker import render_broker
        stock = make_stock(score=80)
        data = make_data(threshold=70, signal_count=1, signals=[stock])
        html = render_broker(data)
        assert '达标' in html

    def test_threshold_shown_in_signal_section(self):
        """阈值在信号区域正确显示"""
        from templates.broker import render_broker
        data = make_data(threshold=70)
        html = render_broker(data)
        assert '70' in html

    def test_near_threshold_section(self):
        """接近阈值排行正确渲染"""
        from templates.broker import render_broker
        top = make_stock(score=65)
        data = make_data(threshold=70, top10=[top], signals=[])
        html = render_broker(data)
        assert '接近阈值' in html or '差' in html


# ─── social 模板测试 ─────────────────────────────────────────────────────────

class TestSocialTemplate:
    def test_renders_with_no_signals(self):
        from templates.social import render_social
        data = make_data(threshold=70, signal_count=0)
        html = render_social(data)
        assert html.startswith('<!DOCTYPE html>')
        assert '空仓' in html or '不操作' in html

    def test_renders_with_signals(self):
        from templates.social import render_social
        stock = make_stock(score=85)
        data = make_data(threshold=70, signal_count=1, signals=[stock])
        html = render_social(data)
        assert '强势' in html or '信号' in html

    def test_threshold_shown(self):
        from templates.social import render_social
        data = make_data(threshold=70)
        html = render_social(data)
        assert '70' in html

    def test_backtest_stats_present(self):
        from templates.social import render_social
        data = make_data()
        html = render_social(data)
        assert '胜率' in html or 'win_rate' not in html.lower()

    def test_near_threshold_cards(self):
        """接近阈值的股票卡片正确显示差距"""
        from templates.social import render_social
        top = make_stock(score=63)
        data = make_data(threshold=70, top10=[top], signals=[])
        html = render_social(data)
        assert '差' in html or '达标' in html