# 网格交易管理系统

基于微信云托管的网格交易策略管理 Web 应用。

## 技术栈

- **后端**: Python 3.11 + Flask
- **数据库**: SQLite（零配置，数据持久化到云托管存储）
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
- `POST /api/stocks` — 创建标的
- `PUT /api/stocks/:id/price` — 更新价格

### 交易记录
- `GET /api/stocks/:id/trades` — 列出交易记录
- `POST /api/stocks/:id/trades` — 添加交易记录
- `DELETE /api/stocks/:id/trades/:tradeId` — 删除交易记录

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
