"""应用配置"""
import os

class Config:
    PORT = int(os.environ.get("PORT", 8000))
    DB_PATH = os.environ.get("DB_PATH", "data/trading.db")

    # 微信测试号
    WECHAT_APPID = os.environ.get("WECHAT_APPID", "wx90563969036d9a65")
    WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "f12f5a129c1c8b9702ef1a4e481d1432")
    WECHAT_TOKEN = os.environ.get("WECHAT_TOKEN", "trading2024")

    # JWT
    JWT_SECRET = os.environ.get("JWT_SECRET", "codes-trading-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_DAYS = 30

    # 公网地址
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000")

config = Config()
