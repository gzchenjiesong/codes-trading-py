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
_marketaux_cache = {"ts": 0, "data": None}
CACHE_TTL = 60  # 1 分钟缓存（金十+财联社）
MARKETAUX_CACHE_TTL = 3600  # 1 小时缓存（Marketaux，配额有限）


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


def get_financial_news(days: int = 2):
    """
    获取财经资讯（金十快讯 + 财联社电报 + Marketaux）。
    days: 金十快讯历史数据回溯天数（不含今天），默认 2 天，解决凌晨跨天数据为空的问题。
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

    # CDN 历史数据：回溯最近 days 天（解决凌晨跨天数据为空）
    for offset in range(1, days + 1):
        try:
            d = datetime.now() - timedelta(days=offset)
            date_url = f"https://cdn-rili.jin10.com/web_data/{d.year}/{d.month:02d}/{d.day:02d}.json"
            resp = httpx.get(date_url, headers=headers, timeout=10)
            data = json.loads(resp.text)
            for item in _parse_jin10_items(data):
                key = item["content"][:20]
                if key not in seen_keys:
                    seen_keys.add(key)
                    news.append(item)
        except Exception as e:
            print(f"jin10 day-{offset} error: {e}")

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

    # Marketaux 国际财经（3页 = 约9条）
    try:
        ma_items = get_marketaux_news(3)
        for item in ma_items:
            key = item.get("url", item["title"][:30])
            if key not in seen_keys:
                seen_keys.add(key)
                news.append(item)
    except Exception as e:
        print(f"marketaux merge error: {e}")

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


def _fetch_marketaux(lang: str, limit: int, after: str, token: str) -> list:
    """单语言 Marketaux 请求（内部辅助）"""
    url = (
        "https://api.marketaux.com/v1/news/all"
        f"?language={lang}&limit={limit}"
        f"&published_after={after}"
        f"&api_token={token}"
    )
    resp = httpx.get(url, timeout=10)
    data = resp.json()
    return data.get("data", [])


def get_marketaux_news(per_lang: int = 3) -> list:
    """获取 Marketaux 国际财经资讯（中英各取 N 条）
    筛选：中文 + 英文，最近2天
    缓存：1 小时（免费 tier 每日仅 100 次配额）
    配额：2 次/小时 = 48 次/天
    """
    import config
    # 1 小时独立缓存
    now = time.time()
    if _marketaux_cache["data"] and (now - _marketaux_cache["ts"]) < 3600:
        return _marketaux_cache["data"]

    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    results = []

    # 中英文分别请求（合在一起时 API 返回英文为主，中文被挤掉）
    for lang in ("zh", "en"):
        try:
            items = _fetch_marketaux(lang, per_lang, two_days_ago, config.MARKETAUX_TOKEN)
            for item in items:
                published = item.get("published_at", "")[:16].replace("T", " ")
                entities = item.get("entities", [])
                symbols = [e["symbol"] for e in entities if e.get("symbol")]
                sentiments = [e.get("sentiment_score", 0) for e in entities if e.get("sentiment_score") is not None]
                avg_sentiment = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0
                title = item.get("title", "")
                desc = item.get("description", "")
                results.append({
                    "id": f"marketaux_{item.get('uuid', '')[:12]}",
                    "title": title,
                    "content": desc,
                    "date": published,
                    "source": item.get("source", "marketaux"),
                    "category": "国际",
                    "important": avg_sentiment > 0.3 or avg_sentiment < -0.3,
                    "url": item.get("url", ""),
                    "stock": ", ".join(symbols[:5]) if symbols else "",
                    "sentiment": avg_sentiment,
                })
        except Exception as e:
            print(f"marketaux {lang} error: {e}")

    _marketaux_cache["ts"] = now
    _marketaux_cache["data"] = results
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
