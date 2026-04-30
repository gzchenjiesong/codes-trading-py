"""
视图层 — 网格交易系统 API
"""
import time
from functools import wraps
from flask import request, redirect, make_response, jsonify, render_template
import jwt
import httpx

from run import app
import config
from wxcloudrun import dao
from wxcloudrun.services.grid import (
    StockInfo, BaseParams, GridStepParams, run_grid_analysis
)
from wxcloudrun.services.fund_data import (
    get_realtime_quotes, get_etf_kline, DEFAULT_WATCHLIST,
)
from wxcloudrun.services.news_data import get_financial_news
from wxcloudrun.services.market_data import (
    get_market_indices, get_index_kline,
    fetch_industry_sectors, fetch_concept_sectors, get_sector_ranking,
)
from wxcloudrun.services.stock_data import (
    get_stock_quote, get_stock_batch_quote, get_stock_kline,
    get_technical_indicators, detect_market,
)
from wxcloudrun.response import make_succ_response, make_err_response


# ── 工具函数 ──

def create_token(openid, user_id):
    payload = {
        "openid": openid, "userId": user_id,
        "exp": int(time.time()) + config.JWT_EXPIRE_DAYS * 86400,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def get_current_user():
    """从 cookie 中提取当前用户"""
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except Exception:
        return None
    return dao.get_user_by_id(payload["userId"])


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return make_err_response("未登录")
        request._user = user
        return f(*args, **kwargs)
    return decorated


# ── 首页 ──

@app.route('/')
def index():
    return render_template('index.html')


# ── Auth ──

@app.route('/api/auth/wechat')
def wechat_login():
    redirect_uri = f"{config.PUBLIC_URL}/api/auth/callback"
    url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={config.WECHAT_APPID}&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=snsapi_userinfo&state=login"
        f"#wechat_redirect"
    )
    return redirect(url)


@app.route('/api/auth/callback')
async def wechat_callback():
    code = request.args.get("code", "")
    if not code:
        return make_err_response("缺少授权码")

    url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": config.WECHAT_APPID, "secret": config.WECHAT_SECRET,
        "code": code, "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        wx_data = resp.json()

    if "openid" not in wx_data:
        return make_err_response(f"微信授权失败: {wx_data.get('errmsg', 'unknown')}")

    openid = wx_data["openid"]
    user = dao.get_user_by_openid(openid)
    if not user:
        user_id = dao.create_user(openid, wx_data.get("nickname", ""), wx_data.get("headimgurl", ""))
        user = dao.get_user_by_id(user_id)

    token = create_token(openid, user["id"])
    resp = make_response(redirect("/"))
    resp.set_cookie("token", token, max_age=30 * 86400, httponly=True, samesite="lax")
    return resp


@app.route('/api/auth/dev-login')
def dev_login():
    openid = "dev_test_openid_001"
    user = dao.get_user_by_openid(openid)
    if not user:
        user_id = dao.create_user(openid, "开发者")
        user = dao.get_user_by_id(user_id)
    token = create_token(openid, user["id"])
    resp = make_response(redirect("/"))
    resp.set_cookie("token", token, max_age=30 * 86400, httponly=True, samesite="lax")
    return resp


@app.route('/api/auth/me')
def auth_me():
    user = get_current_user()
    if user is None:
        return make_err_response("未登录")
    return make_succ_response(user)


# ── Stocks ──

@app.route('/api/stocks', methods=['GET'])
@login_required
def list_stocks():
    stocks = dao.get_stocks_by_user(request._user["id"])
    return make_succ_response(stocks)


@app.route('/api/stocks/<int:stock_id>', methods=['GET'])
@login_required
def get_stock(stock_id):
    stock = dao.get_stock_by_id(stock_id, request._user["id"])
    if not stock:
        return make_err_response("标的不存在")

    trades_data = dao.get_trades_by_stock(stock_id)

    stock_info = StockInfo(code=stock["code"], name=stock["name"], market=stock["market"],
                           price=stock["current_price"])
    base_params = BaseParams(
        base_cash=stock.get("base_cash", 10000.0),
        one_grid_limit=stock.get("one_grid_limit", 1.0),
        max_slump_pct=stock.get("max_slump_pct", 0.2),
        trigger_add_point=stock.get("trigger_add_point", 0.005),
        trading_price_precision=stock.get("trading_price_precision", 3),
        min_batch_count=stock.get("min_batch_count", 100),
        max_rise_pct=stock.get("max_rise_pct", 0.07),
        mode=stock.get("mode", "m1"),
        control=stock.get("control", "ACTIVE"),
        minimum_buy_pct=stock.get("minimum_buy_pct", 0.1),
        clear_step_pct=stock.get("clear_step_pct", 0.25),
        bottom_buy_pct=stock.get("bottom_buy_pct", 0.2),
        interest_year=stock.get("interest_year", 2025),
        interest_rate=stock.get("interest_rate", 0.045),
        interest_step=stock.get("interest_step", 40),
        interest_trigger=stock.get("interest_trigger", 0.85),
    )
    step_params = GridStepParams(
        sgrid_step_pct=stock.get("sgrid_step_pct", 0.05),
        sgrid_retain_count=stock.get("sgrid_retain_count", 0),
        sgrid_add_pct=stock.get("sgrid_add_pct", 0.0),
        mgrid_step_pct=stock.get("mgrid_step_pct", 0.05),
        mgrid_retain_count=stock.get("mgrid_retain_count", 0),
        mgrid_add_pct=stock.get("mgrid_add_pct", 0.0),
        lgrid_step_pct=stock.get("lgrid_step_pct", 0.05),
        lgrid_retain_count=stock.get("lgrid_retain_count", 0),
        lgrid_add_pct=stock.get("lgrid_add_pct", 0.0),
    )
    trade_records = [
        {
            "type": t["type"],
            "date": t["date"],
            "price": t["price"],
            "count": t["count"],
            "grid_label": t.get("grid_label", ""),
            "extra": t.get("extra", ""),
        }
        for t in trades_data
    ]

    # M3 模式才需要读取 grid_defs
    grid_defs = dao.get_grid_defs(stock_id) if base_params.mode == 'm3' else None

    result = run_grid_analysis(
        stock_info, base_params, step_params,
        stock["current_price"], trade_records, grid_defs,
    )
    return make_succ_response({"stock": stock, "gridResult": result})


@app.route('/api/stocks', methods=['POST'])
@login_required
def create_stock():
    body = request.get_json()
    if 'code' not in body or 'name' not in body:
        return make_err_response("缺少必要参数: code, name")
    stock_id = dao.create_stock(request._user["id"], body)
    return make_succ_response({"id": stock_id})


@app.route('/api/stocks/<int:stock_id>/price', methods=['PUT'])
@login_required
def update_price(stock_id):
    body = request.get_json()
    if 'price' not in body:
        return make_err_response("缺少 price 参数")
    dao.update_stock_price(stock_id, request._user["id"], body["price"])
    return make_succ_response({})


# ── Trades ──

@app.route('/api/stocks/<int:stock_id>/trades', methods=['GET'])
@login_required
def list_trades(stock_id):
    stock = dao.get_stock_by_id(stock_id, request._user["id"])
    if not stock:
        return make_err_response("标的不存在")
    trades = dao.get_trades_by_stock(stock_id)
    return make_succ_response(trades)


@app.route('/api/stocks/<int:stock_id>/trades', methods=['POST'])
@login_required
def create_trade(stock_id):
    stock = dao.get_stock_by_id(stock_id, request._user["id"])
    if not stock:
        return make_err_response("标的不存在")
    body = request.get_json()
    if 'type' not in body or 'date' not in body or 'price' not in body or 'count' not in body:
        return make_err_response("缺少必要参数: type, date, price, count")
    trade_id = dao.create_trade(stock_id, body)
    return make_succ_response({"id": trade_id})


@app.route('/api/stocks/<int:stock_id>/trades/<int:trade_id>', methods=['DELETE'])
@login_required
def delete_trade(stock_id, trade_id):
    get_current_user()  # 验证登录
    dao.delete_trade(trade_id)
    return make_succ_response({})


# ── 资讯 ──

@app.route('/news')
def news_page():
    return render_template('news.html')


@app.route('/api/news')
def api_news():
    """财经资讯列表（金十快讯 + 东方财富公告）"""
    news = get_financial_news()
    return make_succ_response(news)


# ── 大盘指数 ──

@app.route('/api/market/indices')
def api_market_indices():
    """大盘指数实时行情（A股+港股+美股）"""
    indices = get_market_indices()
    return make_succ_response(indices)


@app.route('/api/market/index-kline/<code>')
def market_index_kline(code):
    """指数日K线（腾讯财经CDN）"""
    market = request.args.get("market", "cn")
    days = int(request.args.get("days", 120))
    data = get_index_kline(code, market=market, days=days)
    return make_succ_response(data)


# ── 行业/概念板块 ──

@app.route('/api/market/sectors')
def api_all_sectors():
    """全部板块列表（行业+概念）"""
    stype = request.args.get("type", "industry")
    if stype == "concept":
        data = fetch_concept_sectors(limit=100)
    else:
        data = fetch_industry_sectors(limit=100)
    return make_succ_response(data)


@app.route('/api/market/sectors/ranking')
def api_sector_ranking():
    """板块涨跌幅排行"""
    stype = request.args.get("type", "industry")
    top_n = int(request.args.get("top", 10))
    ranking = get_sector_ranking(stype, "change_pct", top_n)
    return make_succ_response(ranking)


# ── 用户关注板块 ──

@app.route('/api/user/sectors', methods=['GET'])
@login_required
def list_user_sectors():
    """获取用户关注板块列表"""
    sectors = dao.get_user_sectors(request._user["id"])
    # 补充实时行情
    industry_data = {s["code"]: s for s in fetch_industry_sectors(200)}
    concept_data = {s["code"]: s for s in fetch_concept_sectors(200)}
    for s in sectors:
        source = industry_data if s["sector_type"] == "industry" else concept_data
        if s["sector_code"] in source:
            market_info = source[s["sector_code"]]
            s["change_pct"] = market_info.get("change_pct", 0)
            s["change"] = market_info.get("change", 0)
            s["turnover"] = market_info.get("turnover", 0)
            s["up_count"] = market_info.get("up_count", 0)
            s["down_count"] = market_info.get("down_count", 0)
        else:
            s["change_pct"] = 0
            s["change"] = 0
    return make_succ_response(sectors)


@app.route('/api/user/sectors', methods=['POST'])
@login_required
def add_sectors():
    """添加关注板块（支持批量）"""
    body = request.get_json()
    if isinstance(body, list):
        # 批量添加
        dao.batch_add_user_sectors(request._user["id"], body)
    elif isinstance(body, dict) and 'code' in body and 'name' in body:
        dao.add_user_sector(
            request._user["id"], body['code'], body['name'],
            body.get('type', 'industry'),
        )
    else:
        return make_err_response("请提供 {code, name, type} 或数组")
    return make_succ_response({})


@app.route('/api/user/sectors', methods=['DELETE'])
@login_required
def remove_sectors():
    """移除关注板块（支持批量）"""
    body = request.get_json()
    if isinstance(body, list):
        dao.batch_remove_user_sectors(request._user["id"], body)
    elif isinstance(body, dict) and 'code' in body:
        dao.remove_user_sector(request._user["id"], body['code'])
    else:
        return make_err_response("请提供 {code} 或 codes 数组")
    return make_succ_response({})


# ── 行情总览 ──

@app.route('/market')
def market_page():
    return render_template('market.html')


@app.route('/api/market/quotes')
def market_quotes():
    """批量实时行情"""
    quotes = get_realtime_quotes()
    return make_succ_response(quotes)


@app.route('/api/market/kline/<code>')
def market_kline(code):
    """K 线数据"""
    market = request.args.get("market", code[:2] if len(code) >= 6 else "sh")
    days = int(request.args.get("days", 120))
    data = get_etf_kline(code, market=market, days=days)
    return make_succ_response(data)


@app.route('/api/debug/jin10')
def debug_jin10():
    """诊断金十快讯 API 连通性"""
    import json as _json
    from datetime import datetime, timedelta
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
        "Referer": "https://www.jin10.com/",
    }
    result = {"flash_newest": None, "cdn_days": []}

    # 测试 flash_newest.js
    try:
        resp = httpx.get("https://www.jin10.com/flash_newest.js", headers=headers, timeout=10, follow_redirects=True)
        raw = resp.text[:300]
        starts_ok = resp.text.strip().startswith("var newest = ")
        result["flash_newest"] = {
            "status": resp.status_code,
            "starts_with_var_newest": starts_ok,
            "preview": raw,
            "content_length": len(resp.text),
        }
    except Exception as e:
        result["flash_newest"] = {"error": str(e)}

    # 测试 CDN 历史数据（最近3天）
    for offset in range(1, 4):
        d = datetime.now() - timedelta(days=offset)
        url = f"https://cdn-rili.jin10.com/web_data/{d.year}/{d.month:02d}/{d.day:02d}.json"
        try:
            resp = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
            data = _json.loads(resp.text) if resp.status_code == 200 else None
            type0_count = len([x for x in data if x.get("type") == 0]) if data else 0
            result["cdn_days"].append({
                "date": d.strftime("%Y-%m-%d"),
                "status": resp.status_code,
                "total_items": len(data) if data else 0,
                "type0_items": type0_count,
            })
        except Exception as e:
            result["cdn_days"].append({"date": d.strftime("%Y-%m-%d"), "error": str(e)})

    return jsonify(result)


# ── A 股行情 API（智兔数服）──

@app.route('/api/stock/quote/<code>')
def stock_quote(code):
    """单只 A 股实时行情"""
    code = code.strip()
    data = get_stock_quote(code)
    if "error" in data:
        return make_err_response(data["error"])
    return make_succ_response(data)


@app.route('/api/stock/batch-quote', methods=['POST'])
def stock_batch_quote():
    """批量获取 A 股实时行情"""
    codes = request.json.get("codes", []) if request.is_json else []
    if not codes:
        return make_err_response("请提供股票代码列表")
    data = get_stock_batch_quote(codes)
    return make_succ_response(data)


@app.route('/api/stock/kline/<code>')
def stock_kline(code):
    """
    A 股 K 线数据
    参数：market(SH/SZ), period(d/w/m/y/5/15/30/60), adjust(n/f/b),
          start(YYYYMMDD), end(YYYYMMDD), limit(int)
    """
    code = code.strip()
    market = request.args.get("market", detect_market(code))
    period = request.args.get("period", "d")
    adjust = request.args.get("adjust", "n")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", type=int)
    data = get_stock_kline(code, market=market, period=period,
                           adjust=adjust, start=start, end=end, limit=limit)
    return make_succ_response(data)


@app.route('/api/stock/indicator/<code>')
def stock_indicator(code):
    """
    A 股技术指标
    参数：market, period, indicator(macd/kdj), adjust, start, end, limit
    """
    code = code.strip()
    market = request.args.get("market", detect_market(code))
    period = request.args.get("period", "d")
    indicator = request.args.get("indicator", "macd")
    adjust = request.args.get("adjust", "n")
    start = request.args.get("start")
    end = request.args.get("end")
    limit = request.args.get("limit", type=int)
    data = get_technical_indicators(code, market=market, period=period,
                                    indicator=indicator, adjust=adjust,
                                    start=start, end=end, limit=limit)
    return make_succ_response(data)
