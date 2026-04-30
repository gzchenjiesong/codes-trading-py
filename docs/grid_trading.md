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
| one_grid_limit | 3.0 | 单网格限制（ grids 数量上限） |
| max_slump_pct | 0.0 | 最大回撤比例 (0%=不限制) |
| trigger_add_point | 0.0 | 触发加点（价格触发点） |
| min_batch_count | 100 | 最小交易单位 |
| trading_price_precision | 3 | 价格小数精度 |
| max_rise_pct | 0.07 | 最大涨幅比例 (7%) |
| minimum_buy_pct | 0.0 | 最小买入比例 |
| clear_step_pct | 0.0 | 清仓步进比例 |
| bottom_buy_pct | 0.0 | 底部买入比例 |
| interest_year | 2025 | 利息年份 |
| interest_rate | 0.0 | 利率 (%) |
| interest_step | 40 | 利息步进 |
| interest_trigger | 0.85 | 利息触发点 |
| mode | m1 | 网格模式 (m1/m2/m3) |

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

### GET `/api/stocks/:id`
返回标的详情 + 网格分析结果

**响应示例：**
```json
{
  "code": 0,
  "data": {
    "stock": {
      "id": 1,
      "code": "159869",
      "name": "游戏ETF",
      "market": "sz",
      "mode": "m1",
      "base_cash": 10000,
      "current_price": 0.856,
      "one_grid_limit": 3,
      "sgrid_step_pct": 0.03,
      "mgrid_step_pct": 0.05,
      "lgrid_step_pct": 0.05,
      "max_slump_pct": 0.0,
      "trigger_add_point": 0.0,
      "minimum_buy_pct": 0.0,
      "clear_step_pct": 0.0,
      "bottom_buy_pct": 0.0,
      "interest_rate": 0.0,
      "interest_interval": null,
      "interest_dividend_reinvest": 0,
      "control": "ACTIVE"
    },
    "gridResult": {
      "grids": [...],
      "holding": [...],
      "records": [...],
      "total_cost": 5000,
      "total_value": 5500,
      "total_profit": 500
    }
  }
}
```

### POST `/api/stocks`
创建新标的

**请求体：**
```json
{
  "code": "159869",
  "name": "游戏ETF",
  "market": "sz",
  "mode": "m1",
  "base_cash": 10000,
  "one_grid_limit": 3,
  "sgrid_step_pct": 0.03,
  "mgrid_step_pct": 0.05,
  "lgrid_step_pct": 0.05,
  "max_slump_pct": 0.0,
  "trigger_add_point": 0.0,
  "minimum_buy_pct": 0.0,
  "clear_step_pct": 0.0,
  "bottom_buy_pct": 0.0,
  "interest_rate": 0.0,
  "interest_interval": null,
  "interest_dividend_reinvest": 0
}
```

### PUT `/api/stocks/:id/price`
更新标的当前价格

**请求体：**
```json
{
  "price": 0.856
}
```

### POST `/api/stocks/:id/trades`
添加交易记录

**请求体：**
```json
{
  "type": "BUY",
  "date": "2026-04-30",
  "price": 0.856,
  "count": 1000,
  "grid_label": "sgrid1",
  "extra": ""
}
```

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
