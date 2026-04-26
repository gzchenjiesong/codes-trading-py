import sqlite3
import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
import config

# 初始化 Flask 应用
app = Flask(__name__, instance_relative_config=True)
# 信任反向代理的 X-Forwarded-* 头（云托管场景）
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['DEBUG'] = config.DEBUG


def get_conn():
    """获取 SQLite 连接"""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        openid TEXT UNIQUE NOT NULL,
        nickname TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        market TEXT DEFAULT 'sz',
        status INTEGER DEFAULT 1,
        current_price REAL DEFAULT 0,
        mode TEXT DEFAULT 'm1',
        base_cash REAL DEFAULT 10000,
        one_grid_limit REAL DEFAULT 0.67,
        max_slump_pct REAL DEFAULT 0.2,
        trigger_add_point REAL DEFAULT 0.005,
        trading_price_precision INTEGER DEFAULT 3,
        min_batch_count INTEGER DEFAULT 100,
        max_rise_pct REAL DEFAULT 0.07,
        sgrid_step_pct REAL DEFAULT 0.05,
        sgrid_retain_count INTEGER DEFAULT 0,
        sgrid_add_pct REAL DEFAULT 0,
        mgrid_step_pct REAL DEFAULT 0.05,
        mgrid_retain_count INTEGER DEFAULT 0,
        mgrid_add_pct REAL DEFAULT 0,
        lgrid_step_pct REAL DEFAULT 0.05,
        lgrid_retain_count INTEGER DEFAULT 0,
        lgrid_add_pct REAL DEFAULT 0,
        control TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        date TEXT NOT NULL,
        grid_label TEXT DEFAULT '',
        price REAL NOT NULL,
        count INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (stock_id) REFERENCES stocks(id)
    );

    CREATE INDEX IF NOT EXISTS idx_stocks_user ON stocks(user_id);
    CREATE INDEX IF NOT EXISTS idx_trades_stock ON trades(stock_id);

    -- 用户关注板块（行业+概念）
    CREATE TABLE IF NOT EXISTS user_sectors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sector_code TEXT NOT NULL,
        sector_name TEXT NOT NULL,
        sector_type TEXT NOT NULL DEFAULT 'industry',
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, sector_code)
    );
    CREATE INDEX IF NOT EXISTS idx_user_sectors ON user_sectors(user_id);
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized")


# 启动时初始化数据库
init_db()

# 加载控制器
from wxcloudrun import views
