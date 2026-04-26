# 关注模块 — watch.md

> ⚠️ **规划中** — 此模块尚未实现，以下为设计方案。

## 设计目标

从市场模块中分离出来的**用户自选标的关注**功能。市场模块聚焦大盘感知，关注模块聚焦个人持仓/跟踪标的。

## 预期功能

### 标的关注列表
- 用户添加关注的 ETF/股票
- 实时显示价格、涨跌幅
- 支持分组管理（如：ETF 组、个股组）

### 标的信息卡
- 实时行情（价格、涨跌幅、成交量）
- 近期 K 线（日/周）
- 关联网格策略（如已创建）

### 与现有功能的关系

| 模块 | 关注点 |
|------|--------|
| 市场模块 | 大盘温度：7 指数 + 板块排行 |
| 关注模块 | 个人视角：我跟踪的标的 |
| 标的模块 | 策略执行：网格交易管理 |

## 数据模型（草案）

```sql
CREATE TABLE user_watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT DEFAULT 'sz',
    group_name TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, code)
);
```

## API 设计（草案）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/watchlist` | 获取关注列表 |
| POST | `/api/watchlist` | 添加关注 |
| DELETE | `/api/watchlist/:code` | 移除关注 |

## 优先级

**Phase 2** — 市场模块稳定后开始开发。
