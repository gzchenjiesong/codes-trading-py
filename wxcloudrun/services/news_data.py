"""
news_data.py — 财经资讯数据获取服务
数据源：金十快讯（最近2天）+ 财联社电报
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
    for kw in ["解锁VIP", "限时折扣", "加入VIP", "立即领取", "点击查看", "活动链接"]:
        if kw in combined:
            return True
    if "activities" in combined and len(_strip_html(content)) < 20:
        return True
    return False


def _parse_jin10_items(data: list) -> list:
    """解析金十快讯原始数据，过滤广告/重复"""
    results = []
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
    return results


def get_financial_news():
    """
    获取财经资讯（金十快讯 + 财联社电报）。
    返回：[{id, title, content, date, source, category, important, url?}, ...]
    按时间倒序，不限数量。
    """
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["ts"]) < CACHE_TTL:
        return _news_cache["data"]

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        "Referer": "https://www.jin10.com/",
    }
    news = []
    seen_keys = set()

    # 今日最新快讯
    try:
        url = "https://www.jin10.com/flash_newest.js"
        resp = httpx.get(url, headers=headers, timeout=10)
        raw = resp.text.strip()
        if raw.startswith("var newest = "):
            raw = raw.replace("var newest = ", "").rstrip(";")
            data = json.loads(raw)
            for item in _parse_jin10_items(data):
                key = item["content"][:20]
                if key not in seen_keys:
                    seen_keys.add(key)
                    news.append(item)
    except Exception as e:
        print(f"jin10 today error: {e}")

    # 昨日历史数据（解决跨天丢失）
    try:
        yesterday = datetime.now() - timedelta(days=1)
        date_url = f"https://cdn-rili.jin10.com/web_data/{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}.json"
        resp = httpx.get(date_url, headers=headers, timeout=10)
        data = json.loads(resp.text)
        for item in _parse_jin10_items(data):
            key = item["content"][:20]
            if key not in seen_keys:
                seen_keys.add(key)
                news.append(item)
    except Exception as e:
        print(f"jin10 yesterday error: {e}")

    # 财联社电报
    try:
        cls_items = get_cls_news(40)
        for item in cls_items:
            key = item["content"][:20]
            if key not in seen_keys:
                seen_keys.add(key)
                news.append(item)
    except Exception as e:
        print(f"cls merge error: {e}")

    # 按时间倒序
    news.sort(key=lambda x: x.get("date", ""), reverse=True)

    _news_cache["ts"] = now
    _news_cache["data"] = news
    return news


def _parse_cls_items(data: list) -> list:
    """解析财联社电报原始数据"""
    results = []
    for item in data:
        # 过滤广告
        if item.get("is_ad", 0) == 1:
            continue
        content = item.get("content", "")
        if not content or len(content) < 5:
            continue
        # 过滤推广内容
        ad_keywords = ["解锁VIP", "限时折扣", "加入VIP", "立即领取", "活动链接"]
        if any(kw in content for kw in ad_keywords):
            continue
        ctime = item.get("ctime", 0)
        dt = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M") if ctime else ""
        is_important = item.get("level", "C") == "A"
        title = item.get("title", "")
        results.append({
            "id": f"cls_{item.get('id', '')}",
            "title": title if title else content[:50] + ("..." if len(content) > 50 else ""),
            "content": content,
            "date": dt,
            "source": "财联社",
            "category": "电报",
            "important": is_important,
            "url": item.get("shareurl", ""),
        })
    return results


def get_cls_news(count: int = 40) -> list:
    """获取财联社电报（最新 N 条）
    使用 curl_cffi 模拟浏览器 TLS 指纹，绕过 WAF 拦截。
    """
    from curl_cffi import requests as cffi_requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.cls.cn/telegraph",
    }
    try:
        url = (
            "https://www.cls.cn/nodeapi/updateTelegraphList"
            "?app=CailianpressWeb&os=web&sv=7.7.5"
            f"&category=&path=/telegraph&type=all&rn={count}"
            "&last_time=0&has_member=false"
        )
        resp = cffi_requests.get(url, headers=headers, timeout=10, impersonate="chrome")
        data = resp.json()
        roll = data.get("data", {}).get("roll_data", [])
        return _parse_cls_items(roll)
    except Exception as e:
        print(f"cls news error: {e}")
        return []
