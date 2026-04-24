"""
fund_data.py — 金融数据获取服务
直接调用公开 HTTP API（腾讯财经 + 东方财富），零额外依赖
"""
import time
import re
import httpx

# ── 用户关注的 ETF/LOF 列表（来源：pytools/format_current_price.py）──
DEFAULT_WATCHLIST = {
    # 指数
    "sh510050": {"name": "上证50ETF",   "ref_price": 3.348, "category": "指数"},
    "sz159901": {"name": "深证100ETF",  "ref_price": 3.636, "category": "指数"},
    "sh562000": {"name": "中证A100ETF", "ref_price": 1.266, "category": "指数"},
    "sz159845": {"name": "中证1000ETF", "ref_price": 3.522, "category": "指数"},
    "sh588380": {"name": "双创50ETF",   "ref_price": 0.923, "category": "指数"},
    "sz159920": {"name": "恒生ETF",     "ref_price": 1.468, "category": "指数"},
    "sh513180": {"name": "恒科ETF",     "ref_price": 0.951, "category": "指数"},
    "sh513500": {"name": "标普500ETF",  "ref_price": 1.819, "category": "指数"},
    "sz159632": {"name": "纳指100ETF",  "ref_price": 1.405, "category": "指数"},
    # 行业
    "sh512880": {"name": "证券ETF",    "ref_price": 1.354, "category": "行业"},
    "sh512760": {"name": "芯片ETF",    "ref_price": 1.503, "category": "行业"},
    "sz159869": {"name": "游戏ETF",    "ref_price": 1.092, "category": "行业"},
    "sh512710": {"name": "军工ETF",    "ref_price": 0.820, "category": "行业"},
    "sz159938": {"name": "医药ETF",    "ref_price": 1.046, "category": "行业"},
    "sz159611": {"name": "电力ETF",    "ref_price": 0.950, "category": "行业"},
    "sh512200": {"name": "地产ETF",    "ref_price": 1.523, "category": "行业"},
    "sz161725": {"name": "白酒LOF",    "ref_price": 0.900, "category": "行业"},
    "sz159870": {"name": "化工ETF",    "ref_price": 0.861, "category": "行业"},
    "sz159852": {"name": "软件ETF",    "ref_price": 0.984, "category": "行业"},
    "sh515880": {"name": "通信ETF",    "ref_price": 2.068, "category": "行业"},
    "sz159326": {"name": "电网设备ETF", "ref_price": 1.482, "category": "行业"},
    # 概念
    "sh515650": {"name": "消费50ETF",   "ref_price": 1.433, "category": "概念"},
    "sh516970": {"name": "基建50ETF",   "ref_price": 1.247, "category": "概念"},
    "sz159875": {"name": "新能源ETF",   "ref_price": 0.750, "category": "概念"},
    "sh562500": {"name": "机器人ETF",   "ref_price": 1.231, "category": "概念"},
    "sz159559": {"name": "机器人50ETF", "ref_price": 1.651, "category": "概念"},
    "sz159819": {"name": "人工智能ETF", "ref_price": 1.298, "category": "概念"},
    "sh513050": {"name": "中概ETF",     "ref_price": 1.790, "category": "概念"},
    # 大宗
    "sz162411": {"name": "油气LOF",     "ref_price": 0.810, "category": "大宗"},
    "sh512400": {"name": "有色ETF",     "ref_price": 1.198, "category": "大宗"},
}

# 简单内存缓存
_cache = {"ts": 0, "data": None}
CACHE_TTL = 30  # 30 秒缓存


def _parse_tencent_quote(raw: str, watchlist: dict) -> dict | None:
    """
    解析腾讯财经实时行情单条数据。
    返回 dict 或 None。
    腾讯格式：v_sh510050="1~上证50ETF华夏~510050~3.018~3.001~2.995~9899961~..."

    字段索引（~ 分隔）：
      0:  市场代码 (1=深, 0=沪, 2=港股...)
      1:  名称
      2:  代码
      3:  现价
      4:  昨收
      5:  今开
      6:  成交量 (手)
      7-8: 买一/卖一量
      9-28: 五档行情 (买五-买一价/量, 卖一-卖五价/量)
      29: 时间戳
      30: 涨跌额
      31: 涨跌幅 (%)
      32: 最高价
      33: 最低价
      34: 成交量/金额
      35: 成交量 (手)
      36: 成交额 (万)
      37: 换手率 (%)
      48: 振幅 (%)
    """
    # 提取 var_name 和数据部分
    m = re.match(r'v_(\w+)="(.+)"', raw.strip())
    if not m:
        return None

    code = m.group(1)
    data_str = m.group(2)

    # 空数据（未交易或无效代码）
    if not data_str or data_str == "":
        return None

    fields = data_str.split("~")
    if len(fields) < 38:
        return None

    info = watchlist.get(code)
    if not info:
        return None

    def f(idx, cast=float, default=0):
        """安全取值"""
        try:
            v = fields[idx].strip()
            return cast(v) if v else default
        except (ValueError, IndexError):
            return default

    prev_close = f(4, default=info["ref_price"])
    current = f(3, default=prev_close)
    change = round(current - prev_close, 4) if prev_close else 0
    change_pct = round(change / prev_close * 100, 2) if prev_close else 0

    # 时间格式化
    ts = fields[29].strip()
    time_str = ""
    if len(ts) >= 12:
        time_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}"

    return {
        "code": code,
        "name": fields[1].strip() or info["name"],
        "market": code[:2],
        "category": info["category"],
        "ref_price": info["ref_price"],
        "current_price": current,
        "prev_close": prev_close,
        "open_price": f(5, default=prev_close),
        "high": f(32),
        "low": f(33),
        "volume": f(35, int),
        "amount": f(36),
        "change": change,
        "change_pct": change_pct,
        "time_str": time_str,
    }


def get_realtime_quotes(watchlist=None):
    """
    批量获取实时行情（腾讯财经 API qt.gtimg.cn）。
    返回列表：[{code, name, market, category, ref_price, current_price, prev_close,
                open_price, high, low, volume, amount, change, change_pct, time_str}, ...]
    """
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    if watchlist is None:
        watchlist = DEFAULT_WATCHLIST

    codes = list(watchlist.keys())
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)

    try:
        resp = httpx.get(url, timeout=10)
        content = resp.content.decode("gbk")
    except Exception:
        # 降级：返回带参考价的空行情
        return [
            {
                "code": c,
                "name": info["name"],
                "market": c[:2],
                "category": info["category"],
                "ref_price": info["ref_price"],
                "current_price": info["ref_price"],
                "prev_close": info["ref_price"],
                "open_price": 0,
                "high": 0,
                "low": 0,
                "volume": 0,
                "amount": 0,
                "change": 0,
                "change_pct": 0,
                "time_str": "获取失败",
            }
            for c, info in watchlist.items()
        ]

    lines = [l for l in content.strip().split("\n") if l.strip()]
    results = []

    for line in lines:
        parsed = _parse_tencent_quote(line, watchlist)
        if parsed:
            results.append(parsed)

    # 按 watchlist 顺序排序
    code_order = {c: i for i, c in enumerate(codes)}
    results.sort(key=lambda x: code_order.get(x["code"], 999))

    _cache["ts"] = now
    _cache["data"] = results
    return results


def get_etf_kline(code, market="sh", days=120, adjust=1):
    """
    获取 ETF K 线数据（东方财富 API）。
    返回列表：[{date, open, close, high, low, volume}, ...]
    注意：部分 Python TLS 指纹会被东方财富 WAF 拦截，云服务器一般无此问题。
    """
    import subprocess
    secid = f"{'1' if market == 'sh' else '0'}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params_str = (
        f"secid={secid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56"
        f"&klt=101&fqt={adjust}&end=20500101&lmt={days}"
    )
    full_url = f"{url}?{params_str}"
    klines_raw = []

    # 策略 1: httpx
    try:
        resp = httpx.get(
            full_url,
            headers={"Referer": "https://quote.eastmoney.com/", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        klines_raw = resp.json().get("data", {}).get("klines", [])
    except Exception:
        # 策略 2: curl 子进程（应对 TLS 指纹拦截）
        try:
            result = subprocess.run(
                ["curl", "-s", "-H", "Referer: https://quote.eastmoney.com/",
                 "--max-time", "10", full_url],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                import json as _json
                data = _json.loads(result.stdout)
                klines_raw = data.get("data", {}).get("klines", [])
        except Exception:
            pass

    results = []
    for k in klines_raw:
        parts = k.split(",")
        if len(parts) >= 6:
            results.append({
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": int(parts[5]),
            })
    return results


def get_fund_nav_history(code, days=30):
    """
    获取基金历史净值（东方财富 API）。
    返回列表：[{date, unit_nav, acc_nav, change_pct}, ...]
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "fundCode": code,
        "pageIndex": "1",
        "pageSize": str(days),
    }
    headers = {"Referer": "https://fund.eastmoney.com/"}

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        items = data.get("Data", {}).get("LSJZList", [])
    except Exception:
        return []

    results = []
    for item in items:
        results.append({
            "date": item.get("FSRQ", ""),
            "unit_nav": float(item["DWJZ"]) if item.get("DWJZ") else 0,
            "acc_nav": float(item["LJJZ"]) if item.get("LJJZ") else 0,
            "change_pct": float(item["JZZZL"]) if item.get("JZZZL") else 0,
        })
    return results
