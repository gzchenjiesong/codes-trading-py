# 资讯模块 — news.md

## 功能概述

财经资讯聚合页面，提供金十数据快讯。纯前端消费 CDN JSON，无需后端复杂处理。

## 页面路由

`GET /news` → `news.html`

## 数据源

### 金十快讯 (CDN)

- **URL**: `https://cdn-rili.jin10.com/web_data/{year}/{month}/{day}.json`
- **格式**: JSON 数组，每条包含 `type`, `time`, `data.content`, `data.pic`
- **type=0**: 普通快讯
- **type≠0**: 重要数据/事件（可视觉区分）
- **免费**: 无认证，CDN 直接访问

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/news` | 财经资讯列表 |

## 页面结构

- 顶部导航栏（与首页一致的 Tab）
- 资讯列表（时间倒序，卡片式布局）
- 底部 Tab 栏（资讯高亮）

## 设计要点

- 数据按天缓存，减少重复请求
- 卡片式展示，时间线排列
- 重要快讯（type≠0）做视觉区分
