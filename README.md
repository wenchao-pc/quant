---
license: mit
sdk: docker
tags:
  - quant
  - stock
models: []
datasets: []
---

# 📈 量化日报系统

多因子评分选股系统，每日自动生成3种风格报告（社交卡片 / 券商晨报 / 黑客终端）。

## 部署

```bash
docker build -t quant-report .
docker run -d -p 8080:80 quant-report
```

访问 `http://localhost:8080`


