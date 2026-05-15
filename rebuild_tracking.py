"""
从 git 历史提取真实 signals，回放重建 tracking.json
"""
import subprocess
import json
import os

QUANT_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKING_PATH = os.path.join(QUANT_DIR, 'quant-report', 'data', 'tracking.json')


def git_show(commit, path):
    r = subprocess.run(['git', 'show', f'{commit}:{path}'], capture_output=True, text=True, cwd=QUANT_DIR)
    return r.stdout if r.returncode == 0 else None


def get_trading_days_count(entry_date_str, today_str):
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_trade_dates(start_date=entry_date_str, end_date=today_str)
        count = 0
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            if row[1] == '1' and row[0] != entry_date_str:
                count += 1
        bs.logout()
        return max(0, count)
    except Exception:
        return 0


# 从 git 历史提取的真实数据：按 commit 顺序
# commit → (date, signals)
GIT_SIGNALS = [
    # 2026-05-11 第一次有信号的报告（大位科技+蓝思）
    ('87cd16c785447f437d68a431921db2b69f69d5fe', '2026-05-11', [
        {'code': '300433', 'name': '蓝思科技', 'total_score': 84.8, 'price': 30.82},
        {'code': '600589', 'name': '大位科技', 'total_score': 71.0, 'price': 13.02},
    ]),
    # 2026-05-11 修正报告（大位科技消失，被蓝思/数据港/烽火取代）
    ('fe36b2afa1e36fb97c000cde51650540de554f8c', '2026-05-11', [
        {'code': '300433', 'name': '蓝思科技', 'total_score': 84.8, 'price': 30.82},
        {'code': '603881', 'name': '数据港', 'total_score': 81.0, 'price': 42.31},
        {'code': '600498', 'name': '烽火通信', 'total_score': 72.0, 'price': 58.61},
    ]),
    # 2026-05-12 只有烽火信号增强
    ('70c1f9a10ec4fcfc697719ccadee82b7ebb0eb26', '2026-05-12', [
        {'code': '600498', 'name': '烽火通信', 'total_score': 72.0, 'price': 59.17},
    ]),
    # 2026-05-12 后续覆盖（空信号）
    ('9a48d4cfdc323ded3ca8d3b77d0b0b78dc03f3d5', '2026-05-12', []),
    # 2026-05-13（空信号）
    ('f34b1ccc2ca7e4d8dc7ed62abe9c33d3f48b48f9', '2026-05-13', []),
    # 2026-05-14（空信号）
    ('3141ffb57c1fd36f65a20cb547463aedfce13386', '2026-05-14', []),
]


def rebuild():
    print("🔍 从 git 历史提取真实 signals...")
    
    # 验证所有 commit 存在
    for commit, date, signals in GIT_SIGNALS:
        path = f'quant-report/reports/{date}/data.json'
        content = git_show(commit, path)
        if content:
            d = json.loads(content)
            actual_sigs = [(s['code'], s['name'], s['total_score']) for s in signals]
            print(f"  ✅ {date} @ {commit[:7]}: {actual_sigs}")
        else:
            print(f"  ❌ {date} @ {commit[:7]}: git show 失败")

    print()
    tracking = {
        'active': [],
        'closed': [],
        'summary': {'total_signals': 0, 'wins': 0, 'total_return': 0}
    }

    for commit, date_str, signals in GIT_SIGNALS:
        print(f"\n📅 回放: {date_str} @ {commit[:7]}")
        print(f"   signals: {[(s['code'], s['name']) for s in signals]}")

        # 补全 signal_history
        for pos in tracking['active'] + tracking['closed']:
            if 'signal_history' not in pos:
                pos['signal_history'] = [{
                    'date': pos['entry_date'],
                    'score': pos.get('entry_score', 0),
                    'price': pos.get('entry_price', 0),
                    'action': '首次入场'
                }]

        today_codes = {sig['code'] for sig in signals}

        # 加入/增强信号
        for sig in signals:
            existing = next((a for a in tracking['active'] if a['code'] == sig['code']), None)
            if existing:
                existing['signal_history'].append({
                    'date': date_str,
                    'score': sig['total_score'],
                    'price': sig['price'],
                    'action': '信号增强-重置计时'
                })
                existing['entry_date'] = date_str
                existing['entry_score'] = sig['total_score']
                existing['days'] = 0
                tracking['summary']['total_signals'] += 1
                print(f"  🔄 {sig['name']}({sig['code']}) 信号增强重置")
                continue

            tracking['active'].append({
                'name': sig['name'],
                'code': sig['code'],
                'entry_date': date_str,
                'entry_price': sig['price'],
                'entry_score': sig['total_score'],
                'current_price': sig['price'],
                'current_return': 0,
                'status': 'holding',
                'days': 0,
                'signal_history': [{
                    'date': date_str,
                    'score': sig['total_score'],
                    'price': sig['price'],
                    'action': '首次入场'
                }]
            })
            tracking['summary']['total_signals'] += 1
            print(f"  ✅ 加入: {sig['name']}({sig['code']}) score={sig['total_score']}")

        # 信号消失=脏数据，清理出场
        stale_active = []
        for pos in tracking['active']:
            if pos['code'] not in today_codes:
                pos['status'] = 'signal_lost'
                pos['exit_date'] = date_str
                pos['exit_reason'] = '信号消失，清理出场'
                tracking['closed'].append(pos)
                print(f"  🧹 清理: {pos['name']}({pos['code']}) 不在signals中 → signal_lost")
            else:
                stale_active.append(pos)
        tracking['active'] = stale_active

        # 超时平仓（>=3交易日）
        still_active = []
        for pos in tracking['active']:
            if pos['entry_date'] == date_str:
                still_active.append(pos)
                continue
            days = get_trading_days_count(pos['entry_date'], date_str)
            if days >= 3:
                pos['status'] = 'timeout'
                pos['exit_date'] = date_str
                pos['exit_reason'] = f'持有{days}天，自动平仓'
                tracking['closed'].append(pos)
                tracking['summary']['total_return'] += pos.get('current_return', 0)
                if pos.get('current_return', 0) > 0:
                    tracking['summary']['wins'] += 1
                print(f"  ⏰ 超时: {pos['name']}({pos['code']}) 持有{days}天 → timeout")
            else:
                pos['days'] = days
                still_active.append(pos)
        tracking['active'] = still_active

    tracking['active'].sort(key=lambda x: x['entry_date'], reverse=True)

    with open(TRACKING_PATH, 'w', encoding='utf-8') as f:
        json.dump(tracking, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 重建完成")
    print(f"   active: {len(tracking['active'])} 只")
    print(f"   closed: {len(tracking['closed'])} 只")
    print(f"   summary: {tracking['summary']}")
    print(f"\n   active持仓:")
    for p in tracking['active']:
        print(f"     {p['name']}({p['code']}) 入场{p['entry_date']}")
    print(f"\n   closed记录:")
    for p in tracking['closed']:
        print(f"     {p['name']}({p['code']}) {p['entry_date']} → {p['exit_date']} {p['exit_reason']}")


if __name__ == '__main__':
    rebuild()
