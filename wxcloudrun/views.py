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
    StockInfo, BaseParams, GridStepParams, TradeRecord, run_grid_analysis
)
from wxcloudrun.services.fund_data import (
    get_realtime_quotes, get_etf_kline, DEFAULT_WATCHLIST,
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
                           status=stock["status"], price=stock["current_price"])
    base_params = BaseParams(
        base_cash=stock["base_cash"], one_grid_limit=stock["one_grid_limit"],
        max_slump_pct=stock["max_slump_pct"], trigger_add_point=stock["trigger_add_point"],
        trading_price_precision=stock["trading_price_precision"],
        min_batch_count=stock["min_batch_count"], max_rise_pct=stock["max_rise_pct"],
        mode=stock["mode"], control=stock["control"])
    step_params = GridStepParams(
        sgrid_step_pct=stock["sgrid_step_pct"],
        sgrid_retain_count=stock["sgrid_retain_count"],
        mgrid_step_pct=stock["mgrid_step_pct"],
        mgrid_retain_count=stock["mgrid_retain_count"],
        lgrid_step_pct=stock["lgrid_step_pct"],
        lgrid_retain_count=stock["lgrid_retain_count"])
    trade_records = [TradeRecord(type=t["type"], date=t["date"],
                                 grid_label=t["grid_label"],
                                 price=t["price"], count=t["count"])
                     for t in trades_data]

    result = run_grid_analysis(stock_info, base_params, step_params,
                               stock["current_price"], trade_records)
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
