"""
A股红涨绿跌颜色规范
- 涨（正数）→ 红色 (red)
- 跌（负数）→ 绿色 (green)
- 平（零）→ 红色
"""


def up_down_color(value: float) -> str:
    """涨跌幅颜色：正数 red，负数/零 green"""
    return 'green' if value < 0 else 'red'


def drawdown_color(max_drawdown: float) -> str:
    """最大回撤颜色：负数（回撤本身就是负）→ green（亏钱），零 → red（无回撤）"""
    return 'green' if max_drawdown < 0 else 'red'