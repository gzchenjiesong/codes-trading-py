"""
stock_data.py — A 股实时行情 + K 线数据服务
数据源：智兔数服 REST API（zhituapi.com）
覆盖：沪深 A 股（不包括 ETF、港股、美股）
"""
import time
import httpx

# ── 配置 ──
ZHITU_TOKEN = "3BD3D113-0089-465F-80BE-DF2579A98480"
ZHITU_BASE = "https://api.zhituapi.com"

# ── 缓存 ──
_QUOTE_CACHE = {}  # {code: {"ts": float, "data": dict}}
_KLINE_CACHE = {}  # {"code.period": {"ts": float, "data": list}}
CACHE_TTL_QUOTE = 60       # 行情 1 分钟
CACHE_TTL_KLINE = 300      # K 线 5 分钟


def _cache_key(*parts):
    return ".".join(str(p) for p in parts)


def _is_cached(cache_dict, key, ttl):
    entry = cache_dict.get(key)
    if entry and (time.time() - entry["ts"]) < ttl:
        return entry["data"]
    return None


def get_stock_quote(code):
    """
    获取单只 A 股实时行情。
    code: 股票代码，如 "600519"（不需要 sh/sz 前缀）
    返回 dict:
        t:  时间, p: 最新价, pc: 昨收, ud: 涨跌额, v: 成交量(万手),
        cje: 成交额, zf: 振幅%, hs: 换手率%, pe: 市盈率, lb: 量比,
        h: 最高价, l: 最低价, o: 开盘价, yc: 昨收, sz: 总市值,
        lt: 流通市值, sjl: 市净率, zdf60: 60日涨跌幅%, zdfnc: 年初至今涨跌幅%
    """
    cached = _is_cached(_QUOTE_CACHE, code, CACHE_TTL_QUOTE)
    if cached:
        return cached

    url = f"{ZHITU_BASE}/hs/real/ssjy/{code}"
    try:
        resp = httpx.get(url, params={"token": ZHITU_TOKEN}, timeout=10)
        data = resp.json()
        if "error" in data:
            return {"error": data["error"], "code": code}
        _QUOTE_CACHE[code] = {"ts": time.time(), "data": data}
        return data
    except Exception as e:
        return {"error": str(e), "code": code}


def get_stock_batch_quote(codes):
    """
    批量获取 A 股实时行情。
    codes: ["600519", "601318", "000001"]
    返回 dict: {code: quote_data, ...}
    """
    results = {}
    uncached = []

    for code in codes:
        cached = _is_cached(_QUOTE_CACHE, code, CACHE_TTL_QUOTE)
        if cached:
            results[code] = cached
        else:
            uncached.append(code)

    # 逐个获取未缓存的（智兔免费版不支持批量接口）
    for code in uncached:
        results[code] = get_stock_quote(code)

    return results


def get_stock_kline(code, market="SH", period="d", adjust="n",
                    start=None, end=None, limit=None):
    """
    获取 A 股 K 线数据。
    code:   股票代码，如 "600519"
    market: 市场，"SH" 或 "SZ"
    period: 分时级别 - "5"/"15"/"30"/"60"(分钟), "d"(日), "w"(周), "m"(月), "y"(年)
    adjust: 复权方式 - "n"(不复权), "f"(前复权), "b"(后复权), "fr"(等比前复权), "br"(等比后复权)
    start:  开始日期，如 "20260101"
    end:    结束日期，如 "20260426"
    limit:  最新条数
    返回列表：[{t, o, h, l, c, v, a, pc}, ...]
        t: 时间, o: 开盘, h: 最高, l: 最低, c: 收盘, v: 成交量, a: 成交额, pc: 前收盘
    """
    cache_key = _cache_key(code, market, period, adjust, start, end, limit)
    cached = _is_cached(_KLINE_CACHE, cache_key, CACHE_TTL_KLINE)
    if cached:
        return cached

    full_code = f"{code}.{market.upper()}"
    url = f"{ZHITU_BASE}/hs/history/{full_code}/{period}/{adjust}"

    params = {"token": ZHITU_TOKEN}
    if start:
        params["st"] = start
    if end:
        params["et"] = end
    if limit:
        params["lt"] = limit

    try:
        resp = httpx.get(url, params=params, timeout=15)
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            return []
        if not isinstance(data, list):
            return []

        _KLINE_CACHE[cache_key] = {"ts": time.time(), "data": data}
        return data
    except Exception as e:
        print(f"stock kline error: {e}")
        return []


def get_stock_kline_daily(code, market="SH", days=120, adjust="n"):
    """获取日线 K 线（最近 N 天）。"""
    # 用较近的起始日期避免返回过量历史数据
    from datetime import datetime, timedelta
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    data = get_stock_kline(code, market, "d", adjust, start=start)
    return data[-days:] if len(data) > days else data


def get_stock_kline_monthly(code, market="SH", months=36, adjust="n"):
    """获取月线 K 线（最近 N 月）。"""
    from datetime import datetime, timedelta
    start = (datetime.now() - timedelta(days=months * 31)).strftime("%Y%m%d")
    data = get_stock_kline(code, market, "m", adjust, start=start)
    return data[-months:] if len(data) > months else data


def get_technical_indicators(code, market="SH", period="d", indicator="macd",
                             adjust="n", start=None, end=None, limit=None):
    """
    获取技术指标。
    indicator: "macd" / "kdj"
    返回列表：[{t, dif, dea, macd, ...}, ...]
    """
    full_code = f"{code}.{market.upper()}"
    url = f"{ZHITU_BASE}/hs/history/{indicator}/{full_code}/{period}/{adjust}"

    params = {"token": ZHITU_TOKEN}
    if start:
        params["st"] = start
    if end:
        params["et"] = end
    if limit:
        params["lt"] = limit

    try:
        resp = httpx.get(url, params=params, timeout=15)
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            return []
        if not isinstance(data, list):
            return []
        return data
    except Exception as e:
        print(f"technical indicator error: {e}")
        return []


def detect_market(code):
    """根据代码判断市场：SH（沪）还是 SZ（深）。"""
    code = str(code).replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    if code.startswith("6") or code.startswith("5") or code.startswith("9"):
        return "SH"
    elif code.startswith("0") or code.startswith("3") or code.startswith("1") or code.startswith("2"):
        return "SZ"
    return "SH"
