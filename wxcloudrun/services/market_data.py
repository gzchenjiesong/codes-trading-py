"""
market_data.py — 大盘指数实时行情
数据源：腾讯财经 qt.gtimg.cn（A股+港股）、新浪国际行情（美股）
"""
import httpx
import time

_INDEX_CACHE = {"ts": 0, "data": None}
CACHE_TTL = 60  # 1 分钟缓存

# 指数配置
INDEX_LIST = [
    # A 股
    {"code": "sh000001", "name": "上证指数", "market": "cn"},
    {"code": "sz399001", "name": "深证成指", "market": "cn"},
    {"code": "sz399006", "name": "创业板指", "market": "cn"},
    {"code": "sz399678", "name": "科创50", "market": "cn"},
    # 港股
    {"code": "hkHSI", "name": "恒生指数", "market": "hk"},
    {"code": "hkHSTECH", "name": "恒生科技", "market": "hk"},
    # 美股
    {"code": ".INX", "name": "标普500", "market": "us"},
    {"code": ".IXIC", "name": "纳斯达克", "market": "us"},
    {"code": ".DJI", "name": "道琼斯", "market": "us"},
]


def _fetch_cn_hk_indices():
    """A 股 + 港股指数（腾讯财经 API）"""
    codes = [i["code"] for i in INDEX_LIST if i["market"] in ("cn", "hk")]
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
                "volume": int(parts[6]) if parts[6] else 0,  # 手
                "amount": float(parts[37]) if parts[37] else 0,  # 万
                "time": parts[30] if len(parts) > 30 else "",
            }
    except Exception as e:
        print(f"cn/hk index fetch error: {e}")
    return results


def _fetch_us_indices():
    """美股指数（新浪国际行情 API）"""
    us_items = [i for i in INDEX_LIST if i["market"] == "us"]
    # 新浪美股代码映射
    sina_map = {
        ".INX": "int_sp500",
        ".IXIC": "int_nasdaq",
        ".DJI": "int_dji",
    }
    sina_codes = [sina_map[i["code"]] for i in us_items]
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
            # 提取 key: var hq_str_int_sp500="..."
            key = line.split("=")[0].split("_")[-1]
            val = line.split('"')[1]
            if not val:
                continue
            fields = val.split(",")
            if len(fields) < 4:
                continue
            # 反向映射
            reverse_map = {"sp500": ".INX", "nasdaq": ".IXIC", "dji": ".DJI"}
            code = reverse_map.get(key, key)
            name = fields[0]
            price = float(fields[1]) if fields[1] else 0
            change = float(fields[2]) if fields[2] else 0
            change_pct = float(fields[3]) if fields[3] else 0
            results[code] = {
                "name": name,
                "code": code,
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "prev_close": price - change,
                "market": "us",
            }
    except Exception as e:
        print(f"us index fetch error: {e}")
    return results


def get_market_indices():
    """
    获取全部大盘指数实时行情。
    返回：[{name, code, price, prev_close, change, change_pct, high, low, volume, amount, market}, ...]
    """
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
            results.append(data)
        else:
            results.append({"name": item["name"], "code": code, "market": item["market"],
                            "price": 0, "change": 0, "change_pct": 0})

    _INDEX_CACHE["ts"] = now
    _INDEX_CACHE["data"] = results
    return results
