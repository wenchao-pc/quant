---
license: mit
sdk: docker
tags:
  - quant
  - stock
models: []
datasets: []
---

# 📈 量化选股日报系统

A股多因子评分选股系统的每日报告展示平台。每日（周一至周五 15:30 cron）自动运行选股策略，生成信号并追踪持仓表现，输出 3 种风格报告页面。

## 技术栈

- **前端**: 纯静态 HTML/CSS/JS，无框架，3 套主题（社交卡片 / 券商晨报 / 黑客终端）
- **后端**: Python（数据获取 + 选股策略 + 报告生成），由 cron job 定时调用
- **数据源**: 腾讯行情（实时）+ 新浪 K 线（日 K）

## 项目结构

```
quant-report/               ← 本仓库（HuggingFace Spaces / ModelScope 部署）
├── index.html               ← 主页（展示所有历史报告）
├── reports/                 ← 每日报告文件夹
│   └── YYYY-MM-DD/
│       ├── data.json        ← 当日完整数据（前端动态加载）
│       ├── social.html      ← 社交卡片风格（默认）
│       ├── broker.html      ← 券商晨报风格
│       └── hacker.html      ← 黑客终端风格
├── data/
│   ├── tracking.json       ← 信号追踪（持仓/平仓记录）
│   └── report-list.json    ← 历史报告索引
├── css/  js/               ← 前端静态资源
└── Dockerfile / nginx.conf  ← 容器部署

quant/                      ← Python 策略代码（不在本仓库）
├── report-generator/
│   ├── generate.py         ← 报告生成入口（cron 调用）
│   └── templates/           ← 3 套 HTML 模板
├── main.py                  ← 选股策略（均线突破/量价配合/连涨/支撑）
└── backtest.py              ← 历史回测
```

## 推送报告

**仅 tracking.json 改动时（信号追踪修复等）：**

```bash
cd ~/.hermes/quant/quant-report
git add data/tracking.json
git commit -m "fix: ..."
git push origin master   # ModelScope
git push hf master:main  # HuggingFace（注意目标分支是 main）
```

**首次或需要同步完整仓库时：**

```bash
# 两个平台都推
git push origin master   # ModelScope
git push hf master:main  # HF Spaces 读 main 分支
```

## 本地运行

```bash
docker build -t quant-report .
docker run -d -p 8080:80 quant-report
# 访问 http://localhost:8080
```

## 定时任务

- Job ID: `c391ae790ac4`
- 周期: `30 15 * * 1-5`（周一至周五 15:30）
- 流程: 清除缓存 → 运行选股 → 生成报告 → 更新 tracking → 推送飞书
