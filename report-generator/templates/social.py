"""社交卡片风格模板（默认风格）"""
import html
import json
from color_utils import up_down_color, drawdown_color


def e(s):
    """HTML转义，防止XSS"""
    return html.escape(str(s))


def render_social(data):
    date = data['date']
    weekday = data.get('weekday', '')
    signals = data.get('signals', [])
    top10 = data.get('top10', [])
    backtest = data.get('backtest', {})
    signal_count = data.get('signal_count', 0)
    total_scanned = data.get('total_scanned', 0)
    market = data.get('market', {})

    # 回测指标颜色：正数绿色，负数红色
    avg_return = backtest.get('avg_return', 0)
    avg_return_str = backtest.get('avg_return_str', str(avg_return))
    max_drawdown = backtest.get('max_drawdown', 0)
    ar_cls = up_down_color(avg_return)
    md_cls = drawdown_color(max_drawdown)
    
    # 大盘概览小卡
    market_cards = ''
    for code, m in market.items():
        cls = 'up' if m.get('change_pct', 0) >= 0 else 'down'
        market_cards += f'''<div class="index-card"><div class="index-name">{e(m.get("name",""))}</div><div class="index-price">{m.get("price",0):,.2f}</div><div class="index-change {cls}">{m.get("change_pct",0):+.2f}%</div></div>\n'''
    
    # 信号大卡
    if signal_count > 0:
        best = signals[0]
        signal_card = f'''<div class="signal-card signal-yes">
<div class="signal-icon">🎯</div>
<div class="signal-title" style="color:#00e676">今日发现 <b>{signal_count}</b> 只强势股</div>
<div class="signal-desc">最高分：<b>{e(best['name'])}</b> {best['total_score']}分 | 得分≥70才推送</div>
</div>'''
    else:
        top_score = max((t.get('total_score', 0) for t in top10), default=0)
        top_name = next((t['name'] for t in top10 if t.get('total_score', 0) == top_score), '')
        signal_card = f'''<div class="signal-card signal-none">
<div class="signal-icon float">🛡️</div>
<div class="signal-title">今日空仓</div>
<div class="signal-desc">
全市场{total_scanned}只股票扫描完毕<br>
最高分{top_score}（{e(top_name)}），未达70分阈值<br>
<b style="color:rgba(255,255,255,.8)">不操作 = 最好的操作</b>
</div>
</div>'''
    
    # 信号股卡片
    signal_cards = ''
    for i, s in enumerate(signals[:5]):
        score_cls = 'score-high' if s['total_score'] >= 80 else 'score-mid'
        change_cls = 'up' if s['change_pct'] > 0 else 'down'
        turnover_yi = s['turnover'] / 1e8
        
        tags = ''
        for strat, score in s.get('scores', {}).items():
            if score > 0:
                tag_cls = 'tag-green' if score >= 20 else 'tag'
                tags += f'<span class="tag {tag_cls}">{e(strat)} ✓</span>'
        
        signal_cards += f'''<div class="stock-card">
<div class="stock-top">
<div class="stock-info"><h3>{e(s['name'])}</h3><span>{e(s['code'])}</span></div>
<div class="score-ring {score_cls}">{s['total_score']}</div>
</div>
<div class="progress-bar"><div class="progress-fill" style="width:{min(s['total_score'],100)}%"></div></div>
<div class="stock-meta">
<span class="{change_cls}">{'▲' if s['change_pct']>0 else '▼'} {s['change_pct']:+.2f}%</span>
<span class="muted">成交{turnover_yi:.1f}亿</span>
<span class="muted">¥{s['price']:.2f}</span>
</div>
<div class="tags">{tags}</div>
</div>\n'''
    
    # 最接近阈值的股票（从top10中选）
    near_cards = ''
    near_stocks = sorted(top10, key=lambda x: x.get('total_score', 0), reverse=True)[:3]
    for s in near_stocks:
        if s.get('total_score', 0) >= 70:
            continue
        score_cls = 'score-mid' if s['total_score'] >= 60 else 'score-low'
        change_cls = 'up' if s['change_pct'] > 0 else 'down'
        turnover_yi = s['turnover'] / 1e8
        gap = 70 - s['total_score']
        
        near_cards += f'''<div class="stock-card">
<div class="stock-top">
<div class="stock-info"><h3>{e(s['name'])}</h3><span>{e(s['code'])}</span></div>
<div class="score-ring {score_cls}">{s['total_score']}</div>
</div>
<div class="progress-bar"><div class="progress-fill" style="width:{min(s['total_score'],100)}%"></div></div>
<div class="stock-meta">
<span class="{change_cls}">{'▲' if s['change_pct']>0 else '▼'} {s['change_pct']:+.2f}%</span>
<span class="muted">成交{turnover_yi:.1f}亿</span>
<span class="muted">差{gap:.0f}分达标</span>
</div>
</div>\n'''
    
    # 信号卡片 和 接近卡片 之间选一个显示
    display_cards = signal_cards if signal_cards else near_cards

    # 活跃TOP10卡片
    top10_cards = ''
    for i, t in enumerate(top10[:10]):
        change_cls = 'up' if t['change_pct'] > 0 else 'down'
        turnover_yi = t['turnover'] / 1e8
        score_color = '#f093fb' if t['total_score'] >= 60 else 'rgba(255,255,255,.5)'
        status = '接近' if t['total_score'] >= 55 else '观望'
        status_color = '#ffd740' if status == '接近' else 'rgba(255,255,255,.2)'
        top10_cards += f'''<div class="stock-card" style="padding:10px 14px">
<div style="display:flex;justify-content:space-between;align-items:center">
<div><span style="color:rgba(255,255,255,.3);font-size:11px;margin-right:6px">#{i+1}</span><b>{e(t['name'])}</b> <span class="muted">{e(t['code'])}</span></div>
<div style="text-align:right"><span style="color:{score_color};font-weight:700">{t['total_score']}</span> <span style="color:{status_color};font-size:11px">{status}</span></div>
</div>
<div class="stock-meta" style="margin-top:4px">
<span class="{change_cls}">{'▲' if t['change_pct']>0 else '▼'} {t['change_pct']:+.2f}%</span>
<span class="muted">成交{turnover_yi:.1f}亿</span>
</div>
</div>\n'''
    
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📈 量化日报 | {date}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:linear-gradient(180deg,#0f0c29,#302b63,#24243e);min-height:100vh;color:#fff;padding:20px}}
.container{{max-width:480px;margin:0 auto}}
.header{{text-align:center;padding:30px 0 20px}}
.avatar{{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#f093fb,#f5576c);margin:0 auto 12px;display:flex;align-items:center;justify-content:center;font-size:28px}}
.header h2{{font-size:18px;font-weight:600}}
.header p{{font-size:13px;color:rgba(255,255,255,.5);margin-top:4px}}
.date-tag{{display:inline-block;background:rgba(255,255,255,.1);border-radius:20px;padding:4px 14px;font-size:12px;color:rgba(255,255,255,.6);margin-top:10px}}
.signal-card{{border-radius:20px;padding:28px;margin:16px 0;text-align:center}}
.signal-none{{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid rgba(255,255,255,.08)}}
.signal-yes{{background:linear-gradient(135deg,#0d3b0d,#1a5c1a);border:1px solid rgba(0,230,118,.2)}}
.signal-icon{{font-size:52px;margin-bottom:10px}}
.signal-title{{font-size:20px;font-weight:700;margin-bottom:6px}}
.signal-desc{{font-size:13px;color:rgba(255,255,255,.5);line-height:1.6}}
.stock-card{{border-radius:16px;padding:20px;margin:12px 0;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08)}}
.stock-top{{display:flex;justify-content:space-between;align-items:center}}
.stock-info h3{{font-size:18px;font-weight:600}}
.stock-info span{{font-size:12px;color:rgba(255,255,255,.4)}}
.score-ring{{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700}}
.score-high{{background:linear-gradient(135deg,#00e676,#69f0ae);color:#000}}
.score-mid{{background:linear-gradient(135deg,#ffd740,#ffab00);color:#000}}
.score-low{{background:rgba(255,255,255,.1);color:rgba(255,255,255,.4)}}
.progress-bar{{height:6px;background:rgba(255,255,255,.1);border-radius:3px;margin:14px 0 8px;overflow:hidden}}
.progress-fill{{height:100%;border-radius:3px;background:linear-gradient(90deg,#f5576c,#f093fb)}}
.stock-meta{{display:flex;gap:16px;font-size:13px}}
.stock-meta .up{{color:#ff5252}}
.stock-meta .down{{color:#00e676}}
.stock-meta .muted{{color:rgba(255,255,255,.35)}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}}
.tag{{padding:4px 10px;border-radius:12px;font-size:11px;background:rgba(255,255,255,.08);color:rgba(255,255,255,.5)}}
.tag-green{{background:rgba(0,230,118,.15);color:#69f0ae}}
.divider{{height:1px;background:rgba(255,255,255,.06);margin:20px 0}}
.section-label{{font-size:13px;color:rgba(255,255,255,.35);margin-bottom:12px;padding-left:4px}}
.stats-row{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:12px 0}}
.stat-item{{background:rgba(255,255,255,.05);border-radius:12px;padding:16px;text-align:center}}
.stat-item .val{{font-size:22px;font-weight:700}}
.stat-item .val.green{{color:#00e676}}
.val.red{{color:#ff5252}}
.stat-item .val.blue{{color:#00d4ff}}
.stat-item .val.yellow{{color:#ffd740}}
.stat-item .label{{font-size:11px;color:rgba(255,255,255,.35);margin-top:4px}}
.advice-card{{background:rgba(255,255,255,.05);border-radius:16px;padding:20px;margin:16px 0;border-left:3px solid #f093fb}}
.advice-card h4{{font-size:14px;margin-bottom:10px;color:#f093fb}}
.advice-card li{{font-size:13px;color:rgba(255,255,255,.6);margin:6px 0;margin-left:16px}}
.index-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}}
.index-card{{background:rgba(255,255,255,.05);border-radius:12px;padding:12px;text-align:center}}
.index-name{{font-size:11px;color:rgba(255,255,255,.4)}}
.index-price{{font-size:16px;font-weight:600;margin:4px 0}}
.index-change{{font-size:13px;font-weight:600}}
.index-change.up{{color:#ff5252}}
.index-change.down{{color:#00e676}}
.nav-header{{position:fixed;top:0;left:0;right:0;height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:100;background:rgba(18,18,26,.95);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.06)}}
.nav-home{{color:rgba(255,255,255,.5);text-decoration:none;font-size:14px;display:flex;align-items:center;gap:6px;transition:color .2s;cursor:pointer}}
.nav-home:hover{{color:rgba(255,255,255,.8)}}
.nav-switch{{display:flex;gap:6px}}
.style-btn{{padding:6px 12px;border:1px solid rgba(255,255,255,.15);border-radius:16px;font-size:11px;background:transparent;cursor:pointer;text-decoration:none;color:rgba(255,255,255,.4);transition:all .2s}}
.style-btn:hover{{border-color:rgba(255,255,255,.3);color:rgba(255,255,255,.6)}}
.style-btn.active{{background:rgba(240,147,251,.2);border-color:#f093fb;color:#f093fb}}
body{{padding-top:56px}}
.footer{{text-align:center;color:rgba(255,255,255,.2);font-size:11px;margin-top:30px;padding:20px}}
@keyframes float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-6px)}}}}
.float{{animation:float 3s ease-in-out infinite}}
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
<span class="style-btn active">社交风</span>
<a href="broker.html" class="style-btn">券商风</a>
<a href="hacker.html" class="style-btn">终端风</a>
</div>
</div>
<div class="container">
<div class="header">
<div class="avatar">📈</div>
<h2>量化日报</h2>
<p>多因子评分 · 只推高置信度信号</p>
<div class="date-tag">{date} {weekday}</div>
<p style="font-size:11px;color:rgba(255,255,255,.4);margin-top:4px">生成: {e(data.get('generated_at',''))}</p>
</div>

<div class="section-label">📊 大盘</div>
<div class="index-row">
{market_cards}
</div>

{signal_card}

<div class="divider"></div>
<div class="section-label">{"🔥 达标信号股" if signal_count > 0 else "⚡ 最接近阈值的股票"}</div>

{display_cards}

<div class="divider"></div>
<div class="section-label">🔥 活跃股TOP10</div>
{top10_cards}

<div class="divider"></div>
<div class="section-label">📈 策略战绩</div>
<div class="stats-row">
<div class="stat-item"><div class="val green">{backtest.get("win_rate",0)}%</div><div class="label">信号胜率(≥70)</div></div>
<div class="stat-item"><div class="val {ar_cls}">{avg_return_str}%</div><div class="label">平均每笔收益</div></div>
<div class="stat-item"><div class="val blue">{backtest.get("sharpe",0)}</div><div class="label">夏普比率</div></div>
<div class="stat-item"><div class="val {md_cls}">{max_drawdown}%</div><div class="label">最大回撤</div></div>
</div>

<div class="advice-card">
<h4>💡 今日操作建议</h4>
<ul>
<li>{"🎯" if signal_count > 0 else "🛡️"} {"关注信号股，明天下午观察买入时机" if signal_count > 0 else "空仓观望，耐心等待信号"}</li>
<li>📐 信号出现时：+5%止盈 / -3%止损，持有2-3天</li>
<li>💸 单只仓位≤20%，不追涨停</li>
<li>⏳ 70+信号平均每周1-2次</li>
</ul>
</div>

<div class="footer">
⚠️ 仅供参考，不构成投资建议<br>
每个交易日15:30自动更新 · <a href="../../index.html" style="color:rgba(255,255,255,.3)">🏠 返回主页</a><br>
❤️ 量化选股系统 v2.0
</div>
</div>
</body>
</html>'''
