# 用户认证模块 — user.md

## 功能概述

处理用户登录、身份认证、会话管理。支持微信 OAuth2 授权登录和开发者快速登录。

## 登录方式

### 1. 微信 OAuth2 登录

**流程：**
1. 前端跳转 `/api/auth/wechat`
2. 后端重定向到微信 OAuth2 授权页（`snsapi_userinfo` scope）
3. 用户授权后微信回调 `/api/auth/callback?code=xxx`
4. 后端用 code 换取 `access_token` + `openid`
5. 查询或创建用户记录
6. 生成 JWT Token，写入 Cookie（30天有效期，httponly）
7. 重定向到首页

**配置项：**
- `WECHAT_APPID` — 微信 AppID
- `WECHAT_SECRET` — 微信 AppSecret
- `PUBLIC_URL` — 公网回调地址

### 2. 开发者快速登录

**端点：** `GET /api/auth/dev-login`

使用固定的 `dev_test_openid_001` 作为 OpenID，自动创建用户并登录。仅用于本地/测试环境。

## 鉴权机制

- **Token 格式：** JWT（HS256）
- **Payload：** `{openid, userId, exp}`
- **有效期：** 30 天（`JWT_EXPIRE_DAYS` 可配置）
- **存储：** Cookie（`token`，httponly，samesite=lax）
- **读取：** `get_current_user()` 从 Cookie 解析 JWT

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/wechat` | 发起微信授权 |
| GET | `/api/auth/callback` | 微信回调处理 |
| GET | `/api/auth/dev-login` | 开发者快速登录 |
| GET | `/api/auth/me` | 获取当前用户信息 |

## 装饰器

- `@login_required` — 验证用户已登录，未登录返回 `{"code": -1, "errorMsg": "未登录"}`
- 登录用户信息挂载到 `request._user`

## 数据库

参见 `README.md` → `users` 表。
