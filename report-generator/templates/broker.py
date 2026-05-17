"""券商晨报风格模板"""
from .common import e, threshold_color, stock_status, change_cls, turnover_yi, signal_gap

def render_broker(data):
    date = data['date']
    weekday = data.get('weekday', '')
    market = data.get('market', {})
    signals = data.get('signals', [])
    top10 = data.get('top10', [])
    backtest = data.get('backtest', {})
    signal_count = data.get('signal_count', 0)
    total_scanned = data.get('total_scanned', 0)
    active_analyzed = data.get('active_analyzed', 80)
    threshold = data.get('threshold', 70)

    # 回测指标颜色
    avg_return = backtest.get('avg_return', 0)
    avg_return_str = backtest.get('avg_return_str', str(avg_return))
    max_drawdown = backtest.get('max_drawdown', 0)
    ar_color = 'color:#c00' if avg_return > 0 else 'color:#090'
    md_color = 'color:#c00' if max_drawdown < 0 else 'color:#090'
    
    # 大盘行
    market_rows = ''
    for code, m in market.items():
        cls = 'up' if m.get('change_pct', 0) > 0 else 'down'
        market_rows += f'''<tr><td style="font-weight:bold">{e(m.get("name",""))}</td><td>{m.get("price",0):,.2f}</td><td class="{cls}">{m.get("change_pct",0):+.2f}%</td><td>{m.get("volume",0):,.0f}</td></tr>\n'''
    
    # 信号状态
    if signal_count > 0:
        signal_html = f'''<div class="signal-box"><div style="font-size:16px;font-weight:bold;color:#c00">🎯 今日{signal_count}只股票达标（≥{threshold}分）</div><p style="margin:8px 0 0;color:#666">建议关注以下信号股，结合大盘趋势和个人判断操作。</p></div>'''
    else:
        top_score = max((t.get('total_score', 0) for t in top10), default=0)
        top_name = next((t['name'] for t in top10 if t.get('total_score', 0) == top_score), '')
        signal_html = f'''<div class="signal-box no-signal"><div style="font-size:16px;font-weight:bold;color:#52c41a">🛡️ 今日无买入信号</div><p style="margin:8px 0 0;color:#666">全市场{total_scanned}只股票中，成交额前{active_analyzed}只活跃股得分均未达到{threshold}分阈值。</p><p style="margin:4px 0 0;color:#666">最高分：{e(top_name)} {top_score}分 | 回测胜率63.6%，宁缺毋滥。</p></div>'''
    
    # 信号股表格
    signal_rows = ''
    for i, s in enumerate(signals[:10]):
        change_cls = 'up' if s['change_pct'] > 0 else 'down'
        turnover_yi = s['turnover'] / 1e8
        signal_rows += f'''<tr class="highlight"><td style="font-weight:bold">{e(s['name'])}({e(s['code'])})</td><td style="color:#c00;font-weight:bold">{s['total_score']}</td><td class="{change_cls}">{s['change_pct']:+.2f}%</td><td>{s['price']:.2f}</td><td>{turnover_yi:.1f}亿</td><td style="color:#c00">✅买入</td></tr>\n'''
    
    # Top10表格
    top10_rows = ''
    for i, t in enumerate(top10[:10]):
        change_cls = 'up' if t['change_pct'] > 0 else 'down'
        turnover_yi = t['turnover'] / 1e8
        score_color = '#c00' if t['total_score'] >= 60 else '#f60' if t['total_score'] >= 40 else '#999'
        status = '接近' if t['total_score'] >= 55 else '观望'
        status_color = '#f60' if status == '接近' else '#999'
        top10_rows += f'''<tr><td>{i+1}</td><td style="font-weight:bold">{e(t['name'])}</td><td style="color:{score_color}">{t['total_score']}</td><td class="{change_cls}">{t['change_pct']:+.2f}%</td><td>{turnover_yi:.1f}亿</td><td style="color:{status_color}">{status}</td></tr>\n'''
    
    # 接近阈值排行（按得分排序top5，<{threshold}分的）
    near_rows = ''
    near_sorted = sorted(top10, key=lambda x: x.get('total_score', 0), reverse=True)[:5]
    for s in near_sorted:
        if s.get('total_score', 0) >= threshold:
            continue
        change_cls = 'up' if s['change_pct'] > 0 else 'down'
        turnover_yi = s['turnover'] / 1e8
        gap = threshold - s['total_score']
        score_color = '#c00' if s['total_score'] >= 60 else '#f60' if s['total_score'] >= 40 else '#999'
        near_rows += f'<tr><td style="font-weight:bold">{s["name"]}({s["code"]})</td><td style="color:{score_color};font-weight:bold">{s["total_score"]}</td><td class="{change_cls}">{s["change_pct"]:+.2f}%</td><td>{turnover_yi:.1f}亿</td><td>差{gap:.0f}分</td></tr>\n'
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📈 量化日报 | {date}</title>
<style>
body{{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#fff;color:#333;margin:0;padding:20px;font-size:14px;overflow-x:hidden;word-break:break-word}}
.container{{max-width:900px;margin:0 auto;width:100%}}
h1{{font-size:20px;border-bottom:2px solid #c00;padding-bottom:10px;margin:0 0 20px}}
h1 span{{color:#c00}}
.section{{margin-bottom:24px}}
.section-title{{font-size:15px;font-weight:bold;background:#f5f5f5;padding:8px 12px;border-left:3px solid #c00;margin:0 0 12px}}
table{{width:100%;min-width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}}
thead,tbody,tr{{display:table;width:100%;table-layout:fixed}}
td,th{{white-space:nowrap}}
th{{background:#fafafa;color:#666;font-weight:normal;text-align:center;padding:8px 10px;border-bottom:1px solid #eee}}
td{{padding:8px 10px;border-bottom:1px solid #eee;text-align:center}}
td:first-child,th:first-child{{text-align:left}}
.up{{color:#c00;font-weight:bold}}
.down{{color:#090;font-weight:bold}}
.highlight{{background:#fff8f0}}
.signal-box{{background:#fffbe6;border:1px solid #ffe58f;border-radius:4px;padding:12px;margin:10px 0}}
.no-signal{{background:#f6ffed;border-color:#b7eb8f}}
.stat-grid{{display:flex;flex-wrap:wrap;gap:12px;margin:10px 0;overflow-x:auto;justify-content:center}}
.stat-card{{background:#fafafa;border-radius:4px;padding:12px;text-align:center;min-width:120px;flex-shrink:0}}
.stat-card .val{{font-size:22px;font-weight:bold;color:#c00;white-space:nowrap}}
.stat-card .label{{font-size:11px;color:#999;margin-top:4px}}
.risk{{color:#999;font-size:12px;line-height:1.8}}
body{{padding-top:56px}}
.footer{{text-align:center;color:#bbb;font-size:11px;margin-top:30px;padding-top:15px;border-top:1px solid #eee}}
.nav-header{{position:fixed;top:0;left:0;right:0;height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:100;background:#fff;border-bottom:1px solid #eee;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.nav-home{{color:#666;text-decoration:none;font-size:14px;display:flex;align-items:center;gap:6px;transition:color .2s;cursor:pointer}}
.nav-home:hover{{color:#c00}}
.nav-switch{{display:flex;gap:6px}}
.style-btn{{padding:6px 12px;border:1px solid #e0e0e0;border-radius:14px;font-size:11px;background:transparent;cursor:pointer;text-decoration:none;color:#999;transition:all .2s}}
.style-btn:hover{{border-color:#c00;color:#c00}}
.style-btn.active{{background:#c00;color:#fff;border-color:#c00}}
</style>
<script charset="UTF-8" id="LA_COLLECT" src="//sdk.51.la/js-sdk-pro.min.js"></script>
<script>LA.init({{id:"3Pf3gbq7pCRUtZy0",ck:"3Pf3gbq7pCRUtZy0"}})</script>
<script type="text/javascript">
(function(c,l,a,r,i,t,y){{
c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
}})(window, document, "clarity", "script", "wdfbljiech");
</script>
</head>
<body>
<div class="nav-header">
<a class="nav-home" onclick="location.href='../../index.html'">🏠 主页</a>
<div class="nav-switch">
<a href="social.html" class="style-btn">社交风</a>
<span class="style-btn active">券商风</span>
<a href="hacker.html" class="style-btn">终端风</a>
</div>
</div>
<div class="container">
<h1>📈 <span>量化日报</span> | {date} {weekday}</h1>
<p style="color:#666;font-size:12px;margin:2px 0">生成时间: {e(data.get('generated_at',''))}</p>

<div class="section">
<div class="section-title">📊 大盘概览</div>
<table>
<tr><th>指数</th><th>最新价</th><th>涨跌幅</th><th>成交额(亿)</th></tr>
{market_rows}
</table>
</div>

<div class="section">
<div class="section-title">🎯 今日选股信号（阈值≥{threshold}分）</div>
{signal_html}
    {"<table><tr><th>股票</th><th>得分</th><th>涨跌幅</th><th>价格</th><th>成交额</th><th>操作</th></tr>" + signal_rows + "</table>" if signals else ""}
</div>

<div class="section">
<div class="section-title">🔥 活跃股TOP10（按成交额排序）</div>
<table>
<tr><th>#</th><th>股票</th><th>得分</th><th>涨跌幅</th><th>成交额</th><th>信号</th></tr>
{top10_rows}
</table>

<div class="section">
<div class="section-title">⚡ 接近阈值排行（按得分排序）</div>
<table>
<tr><th>股票</th><th>得分</th><th>涨跌幅</th><th>成交额</th><th>差距</th></tr>
{near_rows}
</table>
</div>
</div>

<div class="section">
<div class="section-title">📊 策略回测表现</div>
<div class="stat-grid">
<div class="stat-card"><div class="val">{backtest.get("win_rate",0)}%</div><div class="label">信号胜率(≥{threshold})</div></div>
<div class="stat-card"><div class="val" style="{ar_color}">{avg_return_str}%</div><div class="label">平均每笔收益</div></div>
<div class="stat-card"><div class="val">{backtest.get("sharpe",0)}</div><div class="label">夏普比率</div></div>
<div class="stat-card"><div class="val" style="{md_color}">{max_drawdown}%</div><div class="label">最大回撤</div></div>
</div>
<p style="color:#999;font-size:12px">回测期: {backtest.get("period","")} | {backtest.get("total_trades",0)}笔交易 | 盈亏比{backtest.get("profit_factor",0)} | 年化{backtest.get("annualized",0)}%</p>
</div>

<div class="section">
<div class="section-title">💡 操作建议</div>
<div class="risk">
<p>{"❌" if signal_count == 0 else "✅"} <b>今日建议：{"空仓观望" if signal_count == 0 else "关注信号股"}</b></p>
<p>📐 当信号出现时：买入后<strong>+5%止盈，-3%止损</strong>，持有2-3天</p>
<p>💸 单只仓位≤20%，不追涨停，不重仓单票</p>
<p>⏳ 70+信号平均每周出现1-2次，耐心等待</p>
</div>
</div>

<div class="footer">
⚠️ 仅供参考，不构成投资建议 | 量化选股系统 v2.0 | 多因子评分≥{threshold}<br>
每个交易日15:30自动更新 | <a href="../../index.html">🏠 返回主页</a>
</div>
</div>
</body>
</html>'''
