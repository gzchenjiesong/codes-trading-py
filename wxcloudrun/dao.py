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
    """创建标的，自动处理新字段"""
    # 列名和默认值
    columns = [
        ('user_id', None),
        ('code', None),
        ('name', None),
        ('market', 'sz'),
        ('base_cash', 10000),
        ('mode', 'm1'),
        ('one_grid_limit', 3.0),
        ('max_slump_pct', 0.0),
        ('trigger_add_point', 0.0),
        ('trading_price_precision', 3),
        ('min_batch_count', 100),
        ('max_rise_pct', 0.07),
        ('minimum_buy_pct', 0.0),
        ('clear_step_pct', 0.0),
        ('bottom_buy_pct', 0.0),
        ('interest_year', 2025),
        ('interest_rate', 0.0),
        ('interest_step', 40),
        ('interest_trigger', 0.85),
        ('sgrid_step_pct', 0.05),
        ('sgrid_retain_count', 0),
        ('sgrid_add_pct', 0.0),
        ('mgrid_step_pct', 0.05),
        ('mgrid_retain_count', 0),
        ('mgrid_add_pct', 0.0),
        ('lgrid_step_pct', 0.05),
        ('lgrid_retain_count', 0),
        ('lgrid_add_pct', 0.0),
        ('control', 'ACTIVE'),
    ]
    
    # 构建 SQL
    col_names = []
    placeholders = []
    values = []
    
    for col_name, default_val in columns:
        col_names.append(col_name)
        placeholders.append('?')
        
        # 获取值：优先从 data 中取，否则用默认值
        if col_name == 'user_id':
            values.append(user_id)
        elif col_name in ['code', 'name']:
            values.append(data[col_name])  # 必填字段
        else:
            # 转换驼峰命名为下划线
            camel_key = ''.join(['_' + c.lower() if c.isupper() else c for c in col_name]).lstrip('_')
            # 尝试多种可能的 key 格式
            possible_keys = [
                col_name,
                camel_key,
                col_name.replace('_', ''),  # ongridlimit
            ]
            val = None
            for key in possible_keys:
                if key in data:
                    val = data[key]
                    break
            if val is None:
                val = default_val
            values.append(val)
    
    sql = f"INSERT INTO stocks ({', '.join(col_names)}) VALUES ({', '.join(placeholders)})"
    return execute(sql, values)


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
        INSERT INTO trades (stock_id, type, date, grid_label, price, count, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (stock_id, data['type'], data['date'],
          data.get('gridLabel', ''), data['price'], data['count'],
          data.get('extra', '')))


def delete_trade(trade_id):
    return execute("DELETE FROM trades WHERE id = ?", (trade_id,))

def get_grid_defs(stock_id):
    """读取某标的的网格定义（SGRID / MGRID / LGRID）"""
    return query_all(
        "SELECT * FROM grid_defs WHERE stock_id = ? ORDER BY grid_type, level",
        (stock_id,),
    )


# ── User Sectors (关注板块) ──

def get_user_sectors(user_id):
    return query_all(
        "SELECT * FROM user_sectors WHERE user_id = ? ORDER BY sort_order, created_at",
        (user_id,),
    )


def add_user_sector(user_id, sector_code, sector_name, sector_type='industry'):
    try:
        return execute(
            "INSERT INTO user_sectors (user_id, sector_code, sector_name, sector_type) "
            "VALUES (?, ?, ?, ?)",
            (user_id, sector_code, sector_name, sector_type),
        )
    except Exception:
        # 已存在
        return None


def batch_add_user_sectors(user_id, sectors):
    """批量添加关注板块"""
    for s in sectors:
        add_user_sector(
            user_id,
            s['sector_code'],
            s['sector_name'],
            s.get('sector_type', 'industry')
        )


def delete_user_sector(sector_id, user_id):
    return execute(
        "DELETE FROM user_sectors WHERE id = ? AND user_id = ?",
        (sector_id, user_id),
    )
