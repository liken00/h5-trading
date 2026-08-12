# data/ 数据说明

### today.json
每日 9:25 选股数据，H5 首页和"今日选股"页面读取。

### history.jsonl  
每日收盘后的复盘记录，每行一条 JSON 记录。

### 生成流程
```bash
# 1. 生成今日数据（你输入 5 只 + 战法依据）
python build_today.py --demo    # 用示例数据
# 或
python build_today.py 600519 贵州茅台 双二板+MA10 1680 1750 1650 0.35 主线,消费

# 2. 发布到 GitHub Pages（自动 commit + push）
python publish.py
# 或只生成 commit 不 push：
python publish.py --dry-run
```

### 字段说明

#### today.json
| 字段 | 含义 |
|---|---|
| `date` | 日期 YYYY-MM-DD |
| `publish_time` | 发布时间 |
| `title` | 标题 |
| `summary` | 摘要 |
| `stocks[].code` | 股票代码（6 位）|
| `stocks[].name` | 股票名称 |
| `stocks[].strategy` | 战法依据 |
| `stocks[].entry_price` | 买入价 |
| `stocks[].target_price` | 目标价 |
| `stocks[].stop_loss` | 止损价 |
| `stocks[].position` | 仓位 |
| `stocks[].tags` | 标签 |
| `stocks[].note` | 备注 |

#### history.jsonl
每行：
| 字段 | 含义 |
|---|---|
| `date` | 收盘日期 |
| `code` | 股票代码 |
| `name` | 名称 |
| `entry` | 买入价 |
| `close` | 收盘价 |
| `pct` | 涨跌幅 |
| `result` | win/loss/hold |
| `note` | 备注 |

### 自动更新机制
1. 你 9:25 选股 → 给我代码 + 战法
2. 我跑 build_today.py 生成 today.json
4. 我跑 publish.py 推到 GitHub
5. GitHub Pages 30 秒 - 2 分钟内更新
6. 用户访问 https://liken00.github.io/h5-trading/ 看到新数据