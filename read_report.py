import json
d=json.load(open('/home/kuozi/.hermes/quant/quant_data.json'))
print('日期:', d['date'])
print('70+信号数:', d['signal_count'])
print('top10最高分:', max(s['total_score'] for s in d['top10']))
print('=== signals ===')
for s in d['signals']:
    print(f'  信号: {s["name"]} ({s["code"]}): {s["total_score"]}分')
print('=== top5 ===')
for s in sorted(d['top10'], key=lambda x: -x['total_score'])[:5]:
    print(f'  top10: {s["name"]} ({s["code"]}): {s["total_score"]}分')