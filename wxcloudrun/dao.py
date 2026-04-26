"""
数据库访问层 — SQLite CRUD
"""
import logging
from wxcloudrun import get_conn

logger = logging.getLogger('log')


# ── 通用操作 ──

def query_all(sql, params=()):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    conn = get_conn()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


# ── Users ──

def get_user_by_openid(openid):
    return query_one("SELECT * FROM users WHERE openid = ?", (openid,))


def get_user_by_id(user_id):
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def create_user(openid, nickname='', avatar=''):
    return execute(
        "INSERT INTO users (openid, nickname, avatar) VALUES (?, ?, ?)",
        (openid, nickname, avatar),
    )


# ── Stocks ──

def get_stocks_by_user(user_id):
    return query_all("SELECT * FROM stocks WHERE user_id = ? ORDER BY id", (user_id,))


def get_stock_by_id(stock_id, user_id):
    return query_one("SELECT * FROM stocks WHERE id = ? AND user_id = ?", (stock_id, user_id))


def create_stock(user_id, data):
    return execute("""
        INSERT INTO stocks (user_id, code, name, market, base_cash, mode,
            sgrid_step_pct, mgrid_step_pct, lgrid_step_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, data['code'], data['name'],
          data.get('market', 'sz'), data.get('baseCash', 10000),
          data.get('mode', 'm1'),
          data.get('sgridStepPct', 0.05),
          data.get('mgridStepPct', 0.05),
          data.get('lgridStepPct', 0.05)))


def update_stock_price(stock_id, user_id, price):
    return execute(
        "UPDATE stocks SET current_price = ?, updated_at = datetime('now','localtime') "
        "WHERE id = ? AND user_id = ?",
        (price, stock_id, user_id))


# ── Trades ──

def get_trades_by_stock(stock_id):
    return query_all("SELECT * FROM trades WHERE stock_id = ? ORDER BY date", (stock_id,))


def create_trade(stock_id, data):
    return execute("""
        INSERT INTO trades (stock_id, type, date, grid_label, price, count)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (stock_id, data['type'], data['date'],
          data.get('gridLabel', ''), data['price'], data['count']))


def delete_trade(trade_id):
    return execute("DELETE FROM trades WHERE id = ?", (trade_id,))


# ── User Sectors (关注板块) ──

def get_user_sectors(user_id):
    return query_all(
        "SELECT * FROM user_sectors WHERE user_id = ? ORDER BY sort_order, created_at",
        (user_id,),
    )


def add_user_sector(user_id, sector_code, sector_name, sector_type='industry'):
    try:
        return execute(
            "INSERT OR IGNORE INTO user_sectors (user_id, sector_code, sector_name, sector_type) VALUES (?, ?, ?, ?)",
            (user_id, sector_code, sector_name, sector_type),
        )
    except Exception as e:
        print(f"add_user_sector error: {e}")
        return 0


def remove_user_sector(user_id, sector_code):
    return execute(
        "DELETE FROM user_sectors WHERE user_id = ? AND sector_code = ?",
        (user_id, sector_code),
    )


def batch_add_user_sectors(user_id, sectors):
    """批量添加关注板块。sectors: [{code, name, type}, ...]"""
    conn = get_conn()
    try:
        for s in sectors:
            conn.execute(
                "INSERT OR IGNORE INTO user_sectors (user_id, sector_code, sector_name, sector_type) VALUES (?, ?, ?, ?)",
                (user_id, s['code'], s['name'], s.get('type', 'industry')),
            )
        conn.commit()
        return len(sectors)
    finally:
        conn.close()


def batch_remove_user_sectors(user_id, codes):
    """批量移除关注板块"""
    conn = get_conn()
    try:
        placeholders = ','.join('?' * len(codes))
        conn.execute(
            f"DELETE FROM user_sectors WHERE user_id = ? AND sector_code IN ({placeholders})",
            (user_id, *codes),
        )
        conn.commit()
    finally:
        conn.close()
