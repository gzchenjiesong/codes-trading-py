# 网格交易管理系统

基于微信云托管的网格交易策略管理 Web 应用。

## 功能特性

- **三种网格模式**：M1（固定步进）、M2（分段均衡）、M3（手动指定参数）
- **智能网格计算**：自动生成买卖档位，支持小网/中网/大网三网独立计算
- **持仓分析**：实时计算净持仓、成本价、浮盈亏、收益率
- **交易记录**：手动添加买入/卖出记录，支持网格标签
- **市场行情**：查看大盘指数、行业/概念板块排行、关注板块
- **财经资讯**：整合金十快讯、东方财富公告等财经新闻

## 技术栈

- **后端**: Python 3.14 + Flask
- **数据库**: SQLite（零配置，数据持久化到云托管存储）
- **前端**: 原生 HTML/CSS/JavaScript（单页应用）
- **部署**: 微信云托管

## 本地调试

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python3 run.py 0.0.0.0 8080
```

访问 http://localhost:8080

## API 接口

### 认证
- `GET /api/auth/wechat` — 微信 OAuth 登录
- `GET /api/auth/dev-login` — 开发环境登录
- `GET /api/auth/me` — 获取当前用户

### 标的管理
- `GET /api/stocks` — 列出所有标的
- `GET /api/stocks/:id` — 获取标的详情（含网格分析）
- `POST /api/stocks` — 创建标的（支持 M1/M2/M3 模式和高级参数）
- `PUT /api/stocks/:id/price` — 更新价格

**创建标的请求体示例：**
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

### 交易记录
- `GET /api/stocks/:id/trades` — 列出交易记录
- `POST /api/stocks/:id/trades` — 添加交易记录
- `DELETE /api/stocks/:id/trades/:tradeId` — 删除交易记录

### 市场行情
- `GET /api/market/indices` — 大盘指数实时行情
- `GET /api/market/index-kline/:code` — 指数 K 线数据
- `GET /api/market/sectors` — 板块列表（行业/概念）
- `GET /api/market/sectors/ranking` — 板块涨跌幅排行

### 财经资讯
- `GET /api/news` — 财经资讯列表（金十快讯 + 东方财富公告）

### 用户关注板块
- `GET /api/user/sectors` — 获取用户关注板块
- `POST /api/user/sectors` — 添加关注板块

## 部署到微信云托管

1. 在 [微信云托管控制台](https://cloud.weixin.qq.com/cloudrun) 创建服务
2. 选择 Flask 模板
3. 关联本仓库 GitHub
4. 配置环境变量（可选）：
   - `WECHAT_APPID` — 微信测试号 AppID
   - `WECHAT_SECRET` — 微信测试号 AppSecret
   - `JWT_SECRET` — JWT 签名密钥

## 项目结构

```
.
├── Dockerfile                 # 云托管部署配置
├── config.py                  # 应用配置（环境变量）
├── run.py                     # Flask 入口
├── wxcloudrun/                # Flask 应用包
│   ├── __init__.py            # 应用初始化 + 数据库
│   ├── views.py               # API 路由
│   ├── dao.py                 # 数据库操作
│   ├── response.py            # 响应格式
│   └── services/              # 业务逻辑
│       ├── grid.py            # 网格交易核心
│       └── mymath.py          # 数学工具
└── container.config.json      # 微信云托管容器配置
```
