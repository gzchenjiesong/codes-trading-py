"""
news_data.py — 财经资讯数据获取服务
数据源：金十快讯（实时财经快讯）+ 东方财富公告（上市公司公告）
"""
import re
import time
import httpx

_news_cache = {"ts": 0, "data": None}
CACHE_TTL = 60  # 1 分钟缓存


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    text = re.sub(r'<[^>]+>', '', text)
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
    # 含推广链接但无实质内容
    if "activities" in combined and len(_strip_html(content)) < 20:
        return True
    return False


def _fetch_jin10_flash(limit=30):
    """金十快讯 API — 实时财经快讯"""
    results = []
    try:
        # 方式1：最新快讯 JS
        url = "https://www.jin10.com/flash_newest.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            "Referer": "https://www.jin10.com/",
        }
        resp = httpx.get(url, headers=headers, timeout=10)
        raw = resp.text.strip()
        if raw.startswith("var newest = "):
            raw = raw.replace("var newest = ", "").rstrip(";")
            import json as _json
            data = _json.loads(raw)
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
                    "id": item.get("id", ""),
                    "title": content[:30] + ("..." if len(content) > 30 else ""),
                    "content": content,
                    "date": item.get("time", "")[:16],
                    "source": "金十快讯",
                    "category": "快讯",
                    "important": is_important,
                })
    except Exception as e:
        print(f"jin10 flash error: {e}")

    # 方式2：历史数据（补充）
    if len(results) < 10:
        try:
            from datetime import datetime
            now = datetime.now()
            date_url = f"https://cdn-rili.jin10.com/web_data/{now.year}/{now.month:02d}/{now.day:02d}.json"
            resp = httpx.get(date_url, headers=headers, timeout=10)
            import json as _json
            data = _json.loads(resp.text)
            for item in data:
                if _is_ad(item):
                    continue
                if item.get("type") != 0:
                    continue
                content = item.get("data", {}).get("content", "")
                content = _strip_html(content)
                if not content or len(content) < 5:
                    continue
                # 去重
                if any(r["content"][:20] == content[:20] for r in results):
                    continue
                is_important = item.get("important", 0) == 1
                results.append({
                    "id": item.get("id", ""),
                    "title": content[:30] + ("..." if len(content) > 30 else ""),
                    "content": content,
                    "date": item.get("time", "")[:16],
                    "source": "金十快讯",
                    "category": "快讯",
                    "important": is_important,
                })
        except Exception:
            pass

    return results[:limit]


def _fetch_eastmoney_ann(limit=15):
    """东方财富公告 API — 上市公司公告"""
    results = []
    try:
        url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {
            "sr": "-1", "page_size": str(limit), "page_index": "1",
            "client_source": "web", "f_node": "0",
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        for item in data.get("data", {}).get("list", []):
            title = item.get("title_ch") or item.get("title", "")
            if not title:
                continue
            codes = item.get("codes", [])
            company = codes[0].get("short_name", "") if codes else ""
            src = item.get("source_type", "")
            source_map = {"331": "深交所", "333": "上交所", "44": "基金公告"}
            source = source_map.get(src, "公告")
            results.append({
                "id": item.get("art_code", ""),
                "title": title[:30] + ("..." if len(title) > 30 else ""),
                "content": title,
                "date": item.get("display_time", "")[:16],
                "source": source,
                "category": "公告",
                "important": False,
                "company": company,
            })
    except Exception as e:
        print(f"eastmoney ann error: {e}")
    return results


def get_financial_news():
    """
    获取财经资讯（金十快讯 + 东方财富公告）。
    返回：[{id, title, content, date, source, category, important, company?}, ...]
    按时间倒序，最多 40 条。
    """
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["ts"]) < CACHE_TTL:
        return _news_cache["data"]

    news = []
    news.extend(_fetch_jin10_flash(25))
    news.extend(_fetch_eastmoney_ann(15))

    # 按时间倒序
    news.sort(key=lambda x: x.get("date", ""), reverse=True)
    news = news[:40]

    _news_cache["ts"] = now
    _news_cache["data"] = news
    return news
