"""黑客终端风格模板"""
from .common import change_cls_hacker, stock_status, turnover_yi, signal_gap, threshold_color_hacker
from color_utils import up_down_color, drawdown_color

def render_hacker(data):
    date = data['date']
    weekday = data.get('weekday', '')
    market = data.get('market', {})
    signals = data.get('signals', [])
    top10 = data.get('top10', [])
    backtest = data.get('backtest', {})
    generated_at = data.get('generated_at', '')
    signal_count = data.get('signal_count', 0)
    total_scanned = data.get('total_scanned', 0)
    active_analyzed = data.get('active_analyzed', 80)
    threshold = data.get('threshold', 70)

    # 回测指标颜色（hacker风格：涨=red，跌=bright）
    avg_return = backtest.get('avg_return', 0)
    avg_return_str = backtest.get('avg_return_str', str(avg_return))
    max_drawdown = backtest.get('max_drawdown', 0)
    bt_ar_cls = up_down_color(avg_return)
    bt_md_cls = drawdown_color(max_drawdown)
    
    # 大盘
    market_lines = ''
    for code, m in market.items():
        chg_cls = change_cls_hacker(m.get('change_pct', 0))
        name = m.get("name","")
        price = m.get("price",0)
        chg = m.get("change_pct",0)
        market_lines += '  <span class="white">%s</span> <span class="cyan">%10.2f</span> <span class="%s">%+7.2f%%</span>\n' % (name, price, chg_cls, chg)
    
    # ASCII柱状图 TOP5
    bar_lines = ''
    sorted_stocks = sorted(top10, key=lambda x: x.get('total_score', 0), reverse=True)[:5]
    for s in sorted_stocks:
        score = s.get('total_score', 0)
        filled = int(score / 2.5)
        empty = int((100 - score) / 2.5)
        color = threshold_color_hacker(score)
        bar_lines += '<span class="white">%s %s</span> |<span class="%s">%s</span><span class="dim">%s</span> %s\n' % (s["name"], s["code"], color, '█'*filled, '░'*empty, score)
    
    # 信号状态框
    if signal_count > 0:
        best = signals[0]
        signal_box = '''  +-----------------------------------------+
  |                                         |
  |   <span class="red">&#9889; %d SIGNAL(S) DETECTED</span>              |
  |                                         |
  |   Top Signal: <span class="yellow">%s %dpts</span>       |
  |   Threshold:  %2.1f pts                  |
  |   Action:     <span class="red">MONITOR &amp; PREPARE</span>              |
  |                                         |
  +-----------------------------------------+''' % (signal_count, best['name'], best['total_score'], threshold)
    else:
        top_score = max((t.get('total_score', 0) for t in top10), default=0)
        top_name = next((t['name'] for t in top10 if t.get('total_score', 0) == top_score), '')
        gap = signal_gap(top_score, threshold)
        signal_box = '''  +-----------------------------------------+
  |                                         |
  |   <span class="signal-safe">&#10003; CLEAR - NO ACTION REQUIRED</span>         |
  |                                         |
  |   Highest score: <span class="yellow">%.1f</span> %s        |
  |   Threshold:    %2.1f                    |
  |   Gap:          %.1f pts                 |
  |                                         |
  |   <span class="dim">"不操作就是最好的操作"</span>              |
  |                                         |
  +-----------------------------------------+''' % (top_score, top_name, threshold, gap)
    
    # 信号股表格
    signal_table = ''
    if signals:
        rows = ''
        for i, s in enumerate(signals[:10]):
            chg_cls = change_cls_hacker(s['change_pct'])
            turnover_yi_val = turnover_yi(s['turnover'])
            rows += '<tr><td>%02d</td><td>%s</td><td>%s</td><td class="yellow">%s</td><td class="%s">%+.2f%%</td><td class="white">%s</td><td class="red">BUY</td></tr>\n' % (i+1, s["code"], s["name"], s["total_score"], chg_cls, s["change_pct"], turnover_yi_val)
        signal_table = '''<div class="box"><div class="box-title">&#9656; SIGNAL STOCKS</div>
<table class="term-table"><tr><th>#</th><th>TICKER</th><th>NAME</th><th>SCORE</th><th>CHANGE</th><th>Vol(亿)</th><th>ACTION</th></tr>
%s</table></div>''' % rows
    
    # TOP10表格
    top10_rows = ''
    for i, t in enumerate(top10[:10]):
        score = t.get('total_score', 0)
        score_color = threshold_color_hacker(score)
        status_text, _ = stock_status(score)
        chg_cls = change_cls_hacker(t['change_pct'])
        turnover_yi_val = turnover_yi(t['turnover'])
        status = f'<span class="{threshold_color_hacker(score)}">{status_text}</span>'
        top10_rows += '<tr><td>%02d</td><td>%s</td><td>%s</td><td class="%s">%s</td><td class="%s">%+.2f%%</td><td class="white">%s</td><td>%s</td></tr>\n' % (i+1, t["code"], t["name"], score_color, score, chg_cls, t["change_pct"], turnover_yi_val, status)
    
    # 执行状态
    if signal_count > 0:
        exec_status = '<span class="red">STATUS: SIGNAL DETECTED</span>'
        exec_hint = '关注信号股，观察买入时机'
    else:
        exec_status = '<span class="yellow">STATUS: CLEAR</span>'
        exec_hint = '空仓观望，等待下一个信号'
    
    # 用字符串拼接避免f-string花括号问题
    html = '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📈 量化日报 | %(date)s</title>
<style>
* {margin:0;padding:0;box-sizing:border-box}
body {font-family:'Courier New',monospace;background:#000;color:#00ff41;padding:0;font-size:13px;line-height:1.7;overflow-x:hidden}
.container {max-width:780px;margin:0 auto;padding:0 10px;width:100%%}
.bright {color:#00ff41}
.dim {color:#0a6b0a}
p.dim {overflow:hidden}
.cyan {color:#00e5ff}
.red {color:#ff1744}
.yellow {color:#ffd600}
.white {color:#e0e0e0}
.gray {color:#555}
pre {font-family:'Courier New',monospace;font-size:11px;line-height:1.4;margin:8px 0;overflow-x:auto;white-space:pre}
.box {border:1px solid #0a6b0a;padding:16px;margin:12px 0;overflow-x:auto}
.box-title {color:#00e5ff;margin-bottom:8px;font-weight:bold}
.term-table {width:100%%;min-width:100%%;border-collapse:collapse;font-family:'Courier New',monospace;font-size:11px;margin:8px 0;display:block;overflow-x:auto}
.term-table thead,.term-table tbody,.term-table tr {display:table;width:100%%;table-layout:fixed}
.term-table td,.term-table th {white-space:nowrap}
.term-table th {color:#00e5ff;text-align:center;padding:6px 12px;border-bottom:1px dashed #0a6b0a;font-weight:normal}
.term-table td {padding:6px 12px;border-bottom:1px solid #0a2e0a;text-align:center}
.term-table td:first-child,.term-table th:first-child {text-align:left}
.signal-safe {color:#00ff41;text-shadow:0 0 10px rgba(0,255,65,.3)}
.cmd {color:#00e5ff}
.cmd::before {content:'$ ';color:#0a6b0a}
.nav-header {position:fixed;top:0;left:0;right:0;height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:100;background:rgba(0,0,0,.95);border-bottom:1px solid #0a6b0a}
.nav-home {color:#0a6b0a;text-decoration:none;font-size:14px;font-family:Courier New,monospace;transition:color .2s;cursor:pointer}
.nav-home:hover {color:#00ff41}
.nav-switch {display:flex;gap:6px}
.style-btn {padding:6px 12px;border:1px solid #0a3a0a;border-radius:0;font-size:11px;background:transparent;cursor:pointer;text-decoration:none;color:#0a6b0a;font-family:Courier New,monospace;transition:all .2s}
.style-btn:hover {border-color:#00ff41;color:#00ff41}
.style-btn.active {background:#00ff41;color:#000;border-color:#00ff41}
body {padding-top:56px}
.footer {color:#555;font-size:11px;margin-top:30px;padding:20px 0;border-top:1px dashed #0a6b0a}
@keyframes blink {0%%,100%% {opacity:1} 50%% {opacity:0}}
.cursor {animation:blink 1s infinite}
@keyframes scan {0%% {top:0} 100%% {top:100vh}}
.scanline {position:fixed;top:0;left:0;width:100%%;height:2px;background:rgba(0,255,65,0.08);animation:scan 4s linear infinite;pointer-events:none;z-index:100}
</style>
<script charset="UTF-8" id="LA_COLLECT" src="//sdk.51.la/js-sdk-pro.min.js"></script>
<script>LA.init({id:"3Pf3gbq7pCRUtZy0",ck:"3Pf3gbq7pCRUtZy0"})</script>
<script type="text/javascript">
(function(c,l,a,r,i,t,y){
c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
})(window, document, "clarity", "script", "wdfbljiech");
</script>
</head>
<body>
<div class="scanline"></div>
<div class="nav-header">
<a class="nav-home" onclick="location.href='../../index.html'">[HOME]</a>
<div class="nav-switch">
<a href="social.html" class="style-btn">[SOCIAL]</a>
<a href="broker.html" class="style-btn">[BROKER]</a>
<span class="style-btn active">[HACKER]</span>
</div>
</div>
<div class="container">

<pre class="bright">
 ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗████████╗
██╔═══██╗██║   ██║██╔══██╗████╗  ██║╚══██╔══╝
██║   ██║██║   ██║███████║██╔██╗ ██║   ██║   
██║▄▄ ██║██║   ██║██╔══██║██║╚██╗██║   ██║   
╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║   ██║   
 ╚══▄▄═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   
    DAILY SIGNAL REPORT v2.0
</pre>

<p class="dim">═══════════════════════════════════════════════════════════════</p>
<p><span class="cmd">date</span> <span class="white">%(generated_at)s CST</span></p>
<p><span class="cmd">uname</span> <span class="white">QuantSystem 2.0 | Python 3.11 | Tencent+Sina API</span></p>
<p><span class="cmd">wc -l</span> <span class="white">%(total_scanned)d stocks scanned | %(active_analyzed)d active analyzed | 4 strategies</span></p>
<p class="dim">═══════════════════════════════════════════════════════════════</p>

<div class="box">
<div class="box-title">&#9656; MARKET OVERVIEW</div>
<pre>
%(market_lines)s</pre>
</div>

<div class="box">
<div class="box-title">&#9656; SIGNAL STATUS</div>
<pre>
<span class="dim">[SCAN]</span> Running multi-factor analysis on TOP %(active_analyzed)d by volume...
<span class="dim">[SCAN]</span> Strategy 1: MA Breakout ......... <span class="bright">DONE</span>
<span class="dim">[SCAN]</span> Strategy 2: Volume-Price ......... <span class="bright">DONE</span>
<span class="dim">[SCAN]</span> Strategy 3: Consecutive Rally ..... <span class="bright">DONE</span>
<span class="dim">[SCAN]</span> Strategy 4: Support Bounce ........ <span class="bright">DONE</span>
<span class="dim">[SCAN]</span> ─────────────────────────────────────────
<span class="dim">[SCAN]</span> Results: <span class="yellow">%(signal_count)d signals &ge; %(threshold)d</span> | <span class="bright">%(active_analyzed)d stocks scored</span>

%(signal_box)s
</pre>
</div>

<div class="box">
<div class="box-title">&#9656; TOP 5 SCORES</div>
<pre>
%(bar_lines)s                 +──────────────────────────────────────────+
                 0        20        40        60      <span class="red">%(threshold)d THRESHOLD</span>
</pre>
</div>

%(signal_table)s

<div class="box">
<div class="box-title">&#9656; ACTIVE STOCKS TOP 10</div>
<table class="term-table">
<tr><th>#</th><th>TICKER</th><th>NAME</th><th>SCORE</th><th>CHANGE</th><th>Vol(亿)</th><th>STATUS</th></tr>
%(top10_rows)s</table>
</div>

<div class="box">
<div class="box-title">&#9656; BACKTEST STATS</div>
<pre>
  +──────────────────── BACKTEST REPORT ────────────────────+
  │                                                         │
  │  Period:    %(bt_period)s              │
  │  Trades:    <span class="white">%(bt_trades)d</span>              │
  │                                                         │
  │  Win Rate (&ge;%(threshold)d):  <span class="bright">%(bt_wr)5.1f%%</span>  ████████████████░░░░░░░  │
  │  Avg Return:      <span class="%(bt_ar_cls)s">%(avg_return_str)s%%</span> per trade                    │
  │  Sharpe Ratio:    <span class="cyan">%(bt_sh)5.2f</span>                                  │
  │  Max Drawdown:    <span class="%(bt_md_cls)s">%(bt_md)5.2f%%</span>                                │
  │  Profit Factor:   <span class="bright">%(bt_pf)5.2f</span>                                  │
  │  Annualized:      <span class="bright">%(bt_ann)5.1f%%</span>                                │
  │                                                         │
  │  Total Signals:   %(bt_sc)d (in 20 trading days)               │
  │  Avg Frequency:   ~1.5 signals/week                     │
  │                                                         │
  +─────────────────────────────────────────────────────────+
</pre>
</div>

<div class="box">
<div class="box-title">&#9656; EXECUTION PLAN</div>
<pre>
<span class="cmd">cat /etc/quant/rules.conf</span>
  STOP_LOSS    = <span class="red">-3.0%%</span>
  TAKE_PROFIT  = <span class="bright">+5.0%%</span> ~ +10.0%%
  HOLD_PERIOD  = 2 ~ 3 days
  MAX_POSITION = 20%% per stock
  NO_CHASE_LIMIT = true    <span class="dim"># 不追涨停</span>

<span class="cmd">quant --today</span>
  %(exec_status)s
  <span class="dim">→ %(exec_hint)s</span>
  <span class="dim">→ 预计信号周期：1-2次/周</span>
</pre>
</div>

<p class="dim">═══════════════════════════════════════════════════════════════</p>
<div class="footer">
<span class="dim">[EOF]</span> Quant System v2.0 | Tencent+Sina API | MultiFactor &ge;%(threshold)d<br>
<span class="dim">[DISCLAIMER]</span> 仅供参考，不构成投资建议。<br>
<span class="dim">[NEXT]</span> 下个交易日 15:30 CST | <a href="../../index.html" style="color:#0a6b0a">[HOME]</a> <span class="cursor">█</span>
</div>

</div>
</body>
</html>''' % dict(
        date=date,
        generated_at=generated_at,
        total_scanned=total_scanned,
        active_analyzed=active_analyzed,
        signal_count=signal_count,
        market_lines=market_lines,
        signal_box=signal_box,
        bar_lines=bar_lines,
        signal_table=signal_table,
        top10_rows=top10_rows,
        exec_status=exec_status,
        exec_hint=exec_hint,
        bt_period=backtest.get('period', ''),
        bt_trades=backtest.get('total_trades', 0),
        bt_wr=backtest.get('win_rate', 0),
        bt_ar=backtest.get('avg_return', 0),
        avg_return_str=avg_return_str,
        bt_ar_cls=bt_ar_cls,
        bt_sh=backtest.get('sharpe', 0),
        bt_md=backtest.get('max_drawdown', 0),
        bt_md_cls=bt_md_cls,
        bt_pf=backtest.get('profit_factor', 0),
        bt_ann=backtest.get('annualized', 0),
        bt_sc=backtest.get('signal_count', 0),
        threshold=threshold,
    )

    return html
