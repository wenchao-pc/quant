"""三个模板共享的工具函数"""
import html
from color_utils import up_down_color, drawdown_color


def e(s):
    """HTML转义，防止XSS"""
    return html.escape(str(s))


def threshold_color(score, threshold=70):
    """得分对应的颜色class（用于进度环）"""
    if score >= 80:
        return 'score-high'
    if score >= 60:
        return 'score-mid'
    return 'score-low'


def stock_status(score, near=55):
    """股票状态文字和颜色"""
    if score >= near:
        return '接近', '#ffd740'
    return '观望', 'rgba(255,255,255,.2)'


def change_arrow(value):
    """涨跌幅箭头符号"""
    return '▲' if value > 0 else '▼'


def change_cls(value):
    """涨跌幅对应的CSS class（social风格）"""
    return 'up' if value > 0 else 'down'


def turnover_yi(turnover):
    """成交额转为亿元字符串"""
    return f"{turnover / 1e8:.1f}亿"


def threshold_color_hacker(score):
    """得分颜色（hacker风格）"""
    if score >= 60:
        return 'yellow'
    return 'dim'


def signal_gap(score, threshold):
    """离达标的差距分值"""
    return max(threshold - score, 0)


def change_cls_hacker(value):
    """涨跌幅对应的CSS class（hacker风格：涨=red，跌=bright）"""
    return 'red' if value > 0 else 'bright'