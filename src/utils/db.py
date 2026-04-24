"""数据库层 — SQLite"""
import sqlite3
import os
from ..utils.config import config


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
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
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized")


def query(sql: str, params=()):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(sql: str, params=()):
    conn = get_conn()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def execute(sql: str, params=()) -> int:
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id
