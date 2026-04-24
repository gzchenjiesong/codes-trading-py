"""API 路由"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from ..utils import db
from ..utils.config import config
from ..utils.auth import get_current_user, dev_login, create_token, get_wechat_openid
from ..services.grid import (
    StockInfo, BaseParams, GridStepParams, TradeRecord, run_grid_analysis
)

router = APIRouter()


# ── Auth ──

@router.get("/auth/wechat")
async def wechat_login():
    """跳转微信授权"""
    redirect_uri = f"{config.PUBLIC_URL}/api/auth/callback"
    url = (
        f"https://open.weixin.qq.com/connect/oauth2/authorize"
        f"?appid={config.WECHAT_APPID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=snsapi_userinfo"
        f"&state=login"
        f"#wechat_redirect"
    )
    return RedirectResponse(url)


@router.get("/auth/callback")
async def wechat_callback(code: str = "", state: str = ""):
    """微信 OAuth 回调"""
    if not code:
        raise HTTPException(status_code=400, detail="缺少授权码")

    wx_data = await get_wechat_openid(code)
    openid = wx_data["openid"]

    user = db.query_one("SELECT * FROM users WHERE openid = ?", (openid,))
    if not user:
        user_id = db.execute(
            "INSERT INTO users (openid, nickname, avatar) VALUES (?, ?, ?)",
            (openid, wx_data.get("nickname", ""), wx_data.get("headimgurl", "")),
        )
        user = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))

    token = create_token(openid, user["id"])
    resp = RedirectResponse(url="/")
    resp.set_cookie("token", token, max_age=30 * 86400, httponly=True, samesite="lax")
    return resp


@router.get("/auth/dev-login")
async def dev_login_route():
    """开发登录"""
    user, token = dev_login()
    resp = RedirectResponse(url="/")
    resp.set_cookie("token", token, max_age=30 * 86400, httponly=True, samesite="lax")
    return resp


@router.get("/auth/me")
async def auth_me(request: Request):
    """获取当前用户信息"""
    user = get_current_user(request)
    return {"user": user}


# ── Stocks ──

@router.get("/stocks")
async def list_stocks(request: Request):
    user = get_current_user(request)
    stocks = db.query("SELECT * FROM stocks WHERE user_id = ? ORDER BY id", (user["id"],))
    return {"stocks": stocks}


@router.get("/stocks/{stock_id}")
async def get_stock(stock_id: int, request: Request):
    user = get_current_user(request)
    stock = db.query_one("SELECT * FROM stocks WHERE id = ? AND user_id = ?",
                         (stock_id, user["id"]))
    if not stock:
        raise HTTPException(status_code=404, detail="标的不存在")

    trades = db.query("SELECT * FROM trades WHERE stock_id = ? ORDER BY date", (stock_id,))

    # 构建网格分析
    stock_info = StockInfo(code=stock["code"], name=stock["name"], market=stock["market"],
                           status=stock["status"], price=stock["current_price"])
    base_params = BaseParams(
        base_cash=stock["base_cash"], one_grid_limit=stock["one_grid_limit"],
        max_slump_pct=stock["max_slump_pct"], trigger_add_point=stock["trigger_add_point"],
        trading_price_precision=stock["trading_price_precision"],
        min_batch_count=stock["min_batch_count"], max_rise_pct=stock["max_rise_pct"],
        mode=stock["mode"], control=stock["control"],
    )
    step_params = GridStepParams(
        sgrid_step_pct=stock["sgrid_step_pct"],
        sgrid_retain_count=stock["sgrid_retain_count"],
        mgrid_step_pct=stock["mgrid_step_pct"],
        mgrid_retain_count=stock["mgrid_retain_count"],
        lgrid_step_pct=stock["lgrid_step_pct"],
        lgrid_retain_count=stock["lgrid_retain_count"],
    )
    trade_records = [TradeRecord(type=t["type"], date=t["date"],
                                 grid_label=t["grid_label"],
                                 price=t["price"], count=t["count"])
                     for t in trades]

    result = run_grid_analysis(stock_info, base_params, step_params,
                               stock["current_price"], trade_records)

    return {"stock": stock, "gridResult": vars(result)}


@router.post("/stocks")
async def create_stock(request: Request):
    user = get_current_user(request)
    body = await request.json()

    stock_id = db.execute("""
        INSERT INTO stocks (user_id, code, name, market, base_cash, mode,
            sgrid_step_pct, mgrid_step_pct, lgrid_step_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user["id"], body["code"], body["name"],
          body.get("market", "sz"), body.get("baseCash", 10000),
          body.get("mode", "m1"),
          body.get("sgridStepPct", 0.05),
          body.get("mgridStepPct", 0.05),
          body.get("lgridStepPct", 0.05)))

    return {"id": stock_id, "message": "创建成功"}, 201


@router.put("/stocks/{stock_id}/price")
async def update_price(stock_id: int, request: Request):
    user = get_current_user(request)
    body = await request.json()

    db.execute(
        "UPDATE stocks SET current_price = ?, updated_at = datetime('now','localtime') "
        "WHERE id = ? AND user_id = ?",
        (body["price"], stock_id, user["id"]))

    return {"message": "价格更新成功"}


# ── Trades ──

@router.get("/stocks/{stock_id}/trades")
async def list_trades(stock_id: int, request: Request):
    user = get_current_user(request)
    stock = db.query_one("SELECT id FROM stocks WHERE id = ? AND user_id = ?",
                         (stock_id, user["id"]))
    if not stock:
        raise HTTPException(status_code=404, detail="标的不存在")

    trades = db.query("SELECT * FROM trades WHERE stock_id = ? ORDER BY date DESC", (stock_id,))
    return {"trades": trades}


@router.post("/stocks/{stock_id}/trades")
async def create_trade(stock_id: int, request: Request):
    user = get_current_user(request)
    stock = db.query_one("SELECT id FROM stocks WHERE id = ? AND user_id = ?",
                         (stock_id, user["id"]))
    if not stock:
        raise HTTPException(status_code=404, detail="标的不存在")

    body = await request.json()
    trade_id = db.execute("""
        INSERT INTO trades (stock_id, type, date, grid_label, price, count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (stock_id, body["type"], body["date"],
          body.get("gridLabel", ""), body["price"], body["count"]))

    return {"id": trade_id, "message": "记录添加成功"}, 201


@router.delete("/stocks/{stock_id}/trades/{trade_id}")
async def delete_trade(stock_id: int, trade_id: int, request: Request):
    get_current_user(request)  # 验证登录
    db.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    return {"message": "删除成功"}
