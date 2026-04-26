# 网格策略模块 — grid_trading.md

## 功能概述

网格交易核心算法，支持三种模式（M1/M2/M3），计算买卖档位、持仓分析、盈亏统计。

## 核心数据模型

### StockInfo — 标的信息
| 字段 | 说明 |
|------|------|
| code | 标的代码 |
| name | 标的名称 |
| market | 市场 (sz/sh) |
| price | 当前价格 |

### BaseParams — 基础参数
| 字段 | 默认值 | 说明 |
|------|--------|------|
| base_cash | 10000 | 基础资金 |
| one_grid_limit | 0.67 | 单网格资金上限比例 |
| max_slump_pct | 0.2 | 最大跌幅比例 (20%) |
| min_batch_count | 100 | 最小交易单位 |
| trading_price_precision | 3 | 价格小数精度 |
| max_rise_pct | 0.07 | 最大涨幅比例 (7%) |
| mode | m1 | 网格模式 |

### GridStepParams — 网格步进参数
| 字段 | 默认值 | 说明 |
|------|--------|------|
| sgrid_step_pct | 0.05 | 小网步进 (5%) |
| sgrid_retain_count | 0 | 小网保留底仓 |
| mgrid_step_pct | 0.05 | 中网步进 (5%) |
| mgrid_retain_count | 0 | 中网保留底仓 |
| lgrid_step_pct | 0.05 | 大网步进 (5%) |
| lgrid_retain_count | 0 | 大网保留底仓 |

## 网格生成算法

```
对每种网格类型 (sgrid/mgrid/lgrid):
  for level in 1..30:
    buy_price  = align(base_price * (1 - step_pct * level))
    buy_count  = floor((base_cash * one_grid_limit) / buy_price / min_batch) * min_batch
    sell_price = align(buy_price * (1 + step_pct))
    sell_count = max(buy_count - retain_count, 0)
    
    if buy_price < base_price * (1 - max_slump_pct):
      break  # 超过最大跌幅，停止生成
```

### 价格对齐 (align_price)

将计算价格对齐到最小变动价位：
- 精度 3 → 最小变动 0.001
- 精度 2 → 最小变动 0.01

## 持仓分析

从交易记录计算：
- **总买入**: 所有 BUY 记录的金额汇总
- **总卖出**: 所有 SELL 记录的金额汇总
- **净持仓**: 总买入数 - 总卖出数
- **成本价**: 总买入金额 / 总买入数
- **浮盈亏**: 净持仓 × 当前价 - (总买入 - 总卖出)
- **收益率**: 浮盈亏 / 已投入资金

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks/:id` | 标的详情 + 网格分析 |
| PUT | `/api/stocks/:id/price` | 更新价格 |
| GET | `/api/stocks/:id/trades` | 交易记录 |
| POST | `/api/stocks/:id/trades` | 添加交易 |
| DELETE | `/api/stocks/:id/trades/:tid` | 删除交易 |

## 设计要点

- 网格从当前价格向下生成，最多 30 档
- 三网（小/中/大）独立计算，合并排序
- 买入触发：当前价格 ≤ 档位买入价
- 卖出触发：当前价格 ≥ 档位卖出价
- 交易记录手动添加，系统不自动执行交易
