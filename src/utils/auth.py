"""微信 OAuth 认证 + JWT 令牌"""
import time
import httpx
from jose import jwt
from functools import wraps
from fastapi import Request, HTTPException
from ..utils.config import config
from ..utils import db


def create_token(openid: str, user_id: int) -> str:
    payload = {
        "openid": openid,
        "userId": user_id,
        "exp": int(time.time()) + config.JWT_EXPIRE_DAYS * 86400,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期")


async def get_wechat_openid(code: str) -> dict:
    """通过微信 OAuth code 获取 openid"""
    url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": config.WECHAT_APPID,
        "secret": config.WECHAT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if "openid" not in data:
        raise HTTPException(status_code=400, detail=f"微信授权失败: {data.get('errmsg', 'unknown')}")

    return data


async def get_wechat_userinfo(openid: str, access_token: str) -> dict:
    """获取微信用户信息"""
    url = "https://api.weixin.qq.com/sns/userinfo"
    params = {
        "access_token": access_token,
        "openid": openid,
        "lang": "zh_CN",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        return resp.json()


def get_current_user(request: Request) -> dict:
    """从 cookie 中提取当前用户"""
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(token)
    user = db.query_one("SELECT * FROM users WHERE id = ?", (payload["userId"],))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user


def dev_login() -> tuple:
    """开发环境登录，返回 (user, token)"""
    openid = "dev_test_openid_001"
    user = db.query_one("SELECT * FROM users WHERE openid = ?", (openid,))

    if not user:
        user_id = db.execute(
            "INSERT INTO users (openid, nickname) VALUES (?, ?)",
            (openid, "开发者"),
        )
        user = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))

    token = create_token(user["openid"], user["id"])
    return user, token
