"""
news_data.py — 财经资讯数据获取服务
数据源：金十快讯 + 东方财富研报 + 财联社电报
"""
import re
import time
import json
from datetime import datetime, timedelta
import httpx

_news_cache = {"ts": 0, "data": None}
CACHE_TTL = 60  # 1 分钟缓存


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _is_ad(item: dict) -> bool:
    """过滤广告和推广内容"""
    content = item.get("data", {}).get("content", "")
    title = item.get("data", {}).get("title", "")
    combined = content + title
    ad_keywords = ["解锁VIP", "限时折扣", "加入VIP", "立即领取", "点击查看", "活动链接"]
    for kw in ad_keywords:
        if kw in combined:
            return True
    if "activities" in combined and len(_strip_html(content)) < 20:
        return True
    return False


def _fetch_jin10_flash(limit=30):
    """金十快讯 — 实时财经快讯"""
    results = []
    try:
        url = "https://www.jin10.com/flash_newest.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            "Referer": "https://www.jin10.com/",
        }
        resp = httpx.get(url, headers=headers, timeout=10)
        raw = resp.text.strip()
        if raw.startswith("var newest = "):
            raw = raw.replace("var newest = ", "").rstrip(";")
            data = json.loads(raw)
            for item in data:
                if _is_ad(item):
                    continue
                if item.get("type") != 0:
                    continue
                content = item.get("data", {}).get("content", "")
                content = _strip_html(content)
                if not content or len(content) < 5:
                    continue
                is_important = item.get("important", 0) == 1
                results.append({
                    "id": f"jin10_{item.get('id', '')}",
                    "title": content[:50] + ("..." if len(content) > 50 else ""),
                    "content": content,
                    "date": item.get("time", "")[:16],
                    "source": "金十快讯",
                    "category": "快讯",
                    "important": is_important,
                })
    except Exception as e:
        print(f"jin10 flash error: {e}")

    # 补充：昨日历史数据
    if len(results) < 15:
        try:
            yesterday = datetime.now() - timedelta(days=1)
            date_url = f"https://cdn-rili.jin10.com/web_data/{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}.json"
            resp = httpx.get(date_url, headers=headers, timeout=10)
            data = json.loads(resp.text)
            existing_contents = {r["content"][:20] for r in results}
            for item in data:
                if _is_ad(item):
                    continue
                if item.get("type") != 0:
                    continue
                content = item.get("data", {}).get("content", "")
                content = _strip_html(content)
                if not content or len(content) < 5:
                    continue
                if content[:20] in existing_contents:
                    continue
                is_important = item.get("important", 0) == 1
                results.append({
                    "id": f"jin10_{item.get('id', '')}",
                    "title": content[:50] + ("..." if len(content) > 50 else ""),
                    "content": content,
                    "date": item.get("time", "")[:16],
                    "source": "金十快讯",
                    "category": "快讯",
                    "important": is_important,
                })
                existing_contents.add(content[:20])
        except Exception:
            pass

    return results[:limit]


def _fetch_eastmoney_reports(limit=20):
    """东方财富研报 API — 机构研报 / 行业分析"""
    results = []
    try:
        url = "https://reportapi.eastmoney.com/report/list"
        # 按日期倒序，取最近研报
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        date_from = f"{yesterday.strftime('%Y-%m-%d')} 00:00:00"
        params = {
            "industryCode": "*",
            "pageSize": str(limit),
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": date_from,
            "endTime": "",
            "pageNo": "1",
            "fields": "",
            "qType": "1",  # 1=个股研报, 0=行业研报
            "orgCode": "",
            "rcode": "",
            "p": "1",
            "pageNum": "1",
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        for item in data.get("data", []):
            title = item.get("title", "")
            if not title:
                continue
            org_name = item.get("orgSName", "") or item.get("orgName", "")
            info_code = item.get("infoCode", "")
            stock_name = item.get("stockName", "")
            stock_code = item.get("stockCode", "")
            publish_date = item.get("publishDate", "")[:16]
            # 摘要：取前三段或全部
            content = title
            if stock_name:
                content = f"【{stock_name}】{title}"
            results.append({
                "id": f"report_{info_code}",
                "title": title[:50] + ("..." if len(title) > 50 else ""),
                "content": content,
                "date": publish_date,
                "source": org_name or "研报",
                "category": "研报",
                "important": False,
                "stock": stock_name or "",
                "url": f"https://data.eastmoney.com/report/zw/industry.jshtml?infocode={info_code}" if info_code else "",
            })
    except Exception as e:
        print(f"eastmoney reports error: {e}")
    return results[:limit]


def _fetch_cls_telegraph(limit=25):
    """财联社电报 — 实时财经快讯（深度报道版）"""
    results = []
    try:
        url = "https://www.cls.cn/nodeapi/updateTelegraphList"
        params = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "7.7.5",
            "rn": str(limit),
            "last_time": "0",
        }
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.cls.cn/telegraph",
        }
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        rolls = data.get("data", {}).get("roll_data", [])
        for item in rolls:
            content = item.get("content", "")
            title = item.get("title", "") or content[:50]
            content = _strip_html(content)
            if not content or len(content) < 5:
                continue
            ctime = item.get("ctime", 0)
            date_str = ""
            if ctime:
                date_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
            is_important = item.get("level", 0) >= 2  # level >= 2 为重要
            results.append({
                "id": f"cls_{item.get('id', '')}",
                "title": title[:50] + ("..." if len(title) > 50 else ""),
                "content": content,
                "date": date_str,
                "source": "财联社",
                "category": "电报",
                "important": is_important,
            })
    except Exception as e:
        print(f"cls telegraph error: {e}")
    return results[:limit]


def get_financial_news():
    """
    获取财经资讯（金十快讯 + 东方财富研报 + 财联社电报）。
    返回：[{id, title, content, date, source, category, important, ...}, ...]
    按时间倒序，最多 60 条。
    """
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["ts"]) < CACHE_TTL:
        return _news_cache["data"]

    news = []
    news.extend(_fetch_jin10_flash(25))
    news.extend(_fetch_eastmoney_reports(20))
    news.extend(_fetch_cls_telegraph(25))

    # 按时间倒序，去重（按 content 前 20 字去重）
    seen = set()
    deduped = []
    for item in news:
        key = item["content"][:20]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    deduped.sort(key=lambda x: x.get("date", ""), reverse=True)
    deduped = deduped[:60]

    _news_cache["ts"] = now
    _news_cache["data"] = deduped
    return deduped
