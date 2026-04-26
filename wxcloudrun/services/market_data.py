"""
market_data.py — 大盘指数实时行情 + 行业/概念板块数据
数据源：腾讯财经 qt.gtimg.cn（A股+港股）、新浪国际行情（美股）、东方财富（板块）
"""
import httpx
import time
import json

_INDEX_CACHE = {"ts": 0, "data": None}
_SECTOR_CACHE = {"ts": 0, "data": None}
CACHE_TTL = 60  # 1 分钟缓存

# ── 核心指数配置 ──
INDEX_LIST = [
    # A 股
    {"code": "sz000510", "name": "A500",     "market": "cn", "desc": "大盘基准"},
    {"code": "sh932000", "name": "中证2000",  "market": "cn", "desc": "小微盘"},
    {"code": "sh000688", "name": "科创50",    "market": "cn", "desc": "硬科技"},
    # 港股
    {"code": "hkHSI",    "name": "恒生指数",  "market": "hk", "desc": "港股大盘"},
    {"code": "hkHSTECH", "name": "恒生科技",  "market": "hk", "desc": "港股科技"},
    # 美股
    {"code": ".INX",     "name": "标普500",   "market": "us", "desc": "全球锚"},
    {"code": ".IXIC",    "name": "纳斯达克",  "market": "us", "desc": "美股科技"},
]

# ── 同类对比指数（用于发现）──
COMPARE_INDICES = {
    "sz000510": [
        {"code": "sh000300", "name": "沪深300"},
        {"code": "sz399006", "name": "创业板指"},
    ],
    "sh932000": [
        {"code": "sh000905", "name": "中证500"},
        {"code": "sh000852", "name": "中证1000"},
    ],
    "sh000688": [
        {"code": "sz399006", "name": "创业板指"},
    ],
}


# ── 指数实时行情 ──

def _fetch_cn_hk_indices():
    """A 股 + 港股指数（腾讯财经 API）"""
    codes = [i["code"] for i in INDEX_LIST if i["market"] in ("cn", "hk")]
    # 同时拉对比指数
    for comp_list in COMPARE_INDICES.values():
        for comp in comp_list:
            codes.append(comp["code"])
    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    results = {}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        lines = resp.text.strip().split("\n")
        for line in lines:
            if "~" not in line:
                continue
            parts = line.split("~")
            if len(parts) < 40:
                continue
            code = parts[2]
            results[code] = {
                "name": parts[1],
                "code": code,
                "price": float(parts[3]) if parts[3] else 0,
                "prev_close": float(parts[4]) if parts[4] else 0,
                "open": float(parts[5]) if parts[5] else 0,
                "change": float(parts[31]) if parts[31] else 0,
                "change_pct": float(parts[32]) if parts[32] else 0,
                "high": float(parts[33]) if parts[33] else 0,
                "low": float(parts[34]) if parts[34] else 0,
                "volume": int(parts[6]) if parts[6] else 0,
                "amount": float(parts[37]) if parts[37] else 0,
                "time": parts[30] if len(parts) > 30 else "",
            }
    except Exception as e:
        print(f"cn/hk index fetch error: {e}")
    return results


def _fetch_us_indices():
    """美股指数（新浪国际行情 API）"""
    us_items = [i for i in INDEX_LIST if i["market"] == "us"]
    sina_map = {".INX": "int_sp500", ".IXIC": "int_nasdaq", ".DJI": "int_dji"}
    sina_codes = [sina_map.get(i["code"], i["code"]) for i in us_items]
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
    }
    results = {}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        lines = resp.text.strip().split("\n")
        for line in lines:
            if "=" not in line or '"' not in line:
                continue
            key = line.split("=")[0].split("_")[-1]
            val = line.split('"')[1]
            if not val:
                continue
            fields = val.split(",")
            if len(fields) < 4:
                continue
            reverse_map = {"sp500": ".INX", "nasdaq": ".IXIC", "dji": ".DJI"}
            code = reverse_map.get(key, key)
            name = fields[0]
            price = float(fields[1]) if fields[1] else 0
            change = float(fields[2]) if fields[2] else 0
            change_pct = float(fields[3]) if fields[3] else 0
            results[code] = {
                "name": name, "code": code, "price": price,
                "change": change, "change_pct": change_pct,
                "prev_close": price - change, "market": "us",
            }
    except Exception as e:
        print(f"us index fetch error: {e}")
    return results


def get_market_indices():
    """获取全部大盘指数实时行情"""
    now = time.time()
    if _INDEX_CACHE["data"] and (now - _INDEX_CACHE["ts"]) < CACHE_TTL:
        return _INDEX_CACHE["data"]

    cn_hk = _fetch_cn_hk_indices()
    us = _fetch_us_indices()
    all_data = {**cn_hk, **us}

    results = []
    for item in INDEX_LIST:
        code = item["code"]
        if code in all_data:
            data = all_data[code]
            data["market"] = item["market"]
            data["desc"] = item.get("desc", "")
            # 附带对比指数
            if code in COMPARE_INDICES:
                data["compare"] = []
                for comp in COMPARE_INDICES[code]:
                    if comp["code"] in all_data:
                        cd = all_data[comp["code"]]
                        data["compare"].append({
                            "name": comp["name"], "code": comp["code"],
                            "price": cd.get("price", 0),
                            "change_pct": cd.get("change_pct", 0),
                        })
            results.append(data)
        else:
            results.append({
                "name": item["name"], "code": code, "market": item["market"],
                "desc": item.get("desc", ""),
                "price": 0, "change": 0, "change_pct": 0,
            })

    _INDEX_CACHE["ts"] = now
    _INDEX_CACHE["data"] = results
    return results


# ── 指数日K线（腾讯财经CDN）──

_KLINE_CACHE = {}

def get_index_kline(code, market="cn", days=60):
    """
    获取指数日K线（腾讯财经CDN，免费，数据从2000年起）
    code: sz000510 / sh000300 / hkHSI / .INX 等
    返回：[{date, open, close, high, low, volume, amount}, ...]
    """
    cache_key = f"{code}_{market}_{days}"
    now = time.time()
    if cache_key in _KLINE_CACHE and (now - _KLINE_CACHE[cache_key]["ts"]) < 300:
        return _KLINE_CACHE[cache_key]["data"]

    if market == "us":
        return _get_us_index_kline(code, days)

    # A股+港股：腾讯财经CDN日K线
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        data = resp.json()
        stock_data = data.get("data", {}).get(code, {})
        # 尝试 qfqday（前复权），回退 day
        klines = stock_data.get("qfqday") or stock_data.get("day") or []
        results = []
        for k in klines:
            if len(k) >= 6:
                results.append({
                    "date": k[0],
                    "open": float(k[1]),
                    "close": float(k[2]),
                    "high": float(k[3]),
                    "low": float(k[4]),
                    "volume": float(k[5]) if k[5] else 0,
                })
        _KLINE_CACHE[cache_key] = {"ts": now, "data": results}
        return results
    except Exception as e:
        print(f"index kline error [{code}]: {e}")
        return []


def _get_us_index_kline(code, days=60):
    """美股指数日K线（新浪财经）"""
    sina_map = {".INX": "int_sp500", ".IXIC": "int_nasdaq", ".DJI": "int_dji"}
    sina_code = sina_map.get(code, code)
    url = f"https://stock2.finance.sina.com.cn/usstock/api/jsonp.php/IO.XSRV2.CallbackList/US_CategoryService.getList?symbol={sina_code}&page=1&num={days}&sort=date&asc=0"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        # 新浪返回 JSONP，提取 JSON 部分
        text = resp.text
        start = text.find("(") + 1
        end = text.rfind(")")
        if start > 0 and end > start:
            json_str = text[start:end]
            data = json.loads(json_str)
            results = []
            for item in data:
                results.append({
                    "date": item.get("date", ""),
                    "open": float(item.get("open", 0)),
                    "close": float(item.get("close", 0)),
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "volume": float(item.get("volume", 0)),
                })
            return results
    except Exception as e:
        print(f"us kline error [{code}]: {e}")
    return []


# ── 行业板块（东方财富）──

_SECTOR_CACHE = {"industry": {"ts": 0, "data": None}, "concept": {"ts": 0, "data": None}}

def fetch_industry_sectors(limit=50):
    """
    获取 A 股行业板块行情（东方财富）
    返回：[{code, name, change_pct, turnover, volume, amount, ...}, ...]
    """
    cache = _SECTOR_CACHE["industry"]
    now = time.time()
    if cache["data"] and (now - cache["ts"]) < CACHE_TTL:
        return cache["data"][:limit]

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3", "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f8,f12,f14,f104,f105,f128,f136,f140,f141",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        results = []
        for item in items:
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "change": item.get("f4", 0),
                "turnover": item.get("f8", 0),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "type": "industry",
            })
        cache["data"] = results
        cache["ts"] = now
        return results[:limit]
    except Exception as e:
        print(f"industry fetch error: {e}")
        return cache["data"] or []


def fetch_concept_sectors(limit=50):
    """
    获取 A 股概念板块行情（东方财富）
    """
    cache = _SECTOR_CACHE["concept"]
    now = time.time()
    if cache["data"] and (now - cache["ts"]) < CACHE_TTL:
        return cache["data"][:limit]

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": limit, "po": 1, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3", "fs": "m:90+t:3",
        "fields": "f2,f3,f4,f8,f12,f14,f104,f105",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("diff", [])
        results = []
        for item in items:
            results.append({
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "change": item.get("f4", 0),
                "turnover": item.get("f8", 0),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "type": "concept",
            })
        cache["data"] = results
        cache["ts"] = now
        return results[:limit]
    except Exception as e:
        print(f"concept fetch error: {e}")
        return cache["data"] or []


def get_sector_ranking(sector_type="industry", sort_by="change_pct", top_n=10):
    """获取板块涨跌幅排行"""
    if sector_type == "industry":
        data = fetch_industry_sectors(limit=100)
    else:
        data = fetch_concept_sectors(limit=100)

    if sort_by == "change_pct":
        sorted_data = sorted(data, key=lambda x: x.get("change_pct", 0), reverse=True)
    elif sort_by == "turnover":
        sorted_data = sorted(data, key=lambda x: x.get("turnover", 0), reverse=True)
    else:
        sorted_data = data

    return {
        "top": sorted_data[:top_n],
        "bottom": sorted_data[-top_n:][::-1] if len(sorted_data) > top_n else [],
    }
