"""
消费50ETF (515650) 测试数据脚本
执行后：清除旧数据 → 插入 stock + trades + grid_defs
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), "data", "trading.db")

# ── 1. 建 grid_defs 表（如果不存在）──────────────────
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS grid_defs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id       INTEGER NOT NULL,
    grid_type      TEXT    NOT NULL,   -- sgrid / mgrid / lgrid
    level          INTEGER NOT NULL,   -- 0,1,2...
    label          TEXT,               -- 如 "小网0"
    pct_of_base    REAL,              -- 买入价占基价比例，如 1.0=100%
    step_pct       REAL,              -- 卖出步进（小数），如 0.06=6%
    limit_count    REAL,              -- one_grid_limit 对应该档
    UNIQUE(stock_id, grid_type, level),
    FOREIGN KEY (stock_id) REFERENCES stocks(id)
)""")
conn.commit()
print("✅ grid_defs 表就绪")

# ── 2. 清除 id=1 旧数据 ──────────────────────────────────
cur.execute("DELETE FROM grid_defs WHERE stock_id = 1")
cur.execute("DELETE FROM trades     WHERE stock_id = 1")
cur.execute("DELETE FROM stocks     WHERE id = 1")
print("🗑️  已清除 stock#1 旧数据")

# ── 3. 插入 stock ─────────────────────────────────────────
# mode_three , 515650 , 消费50ETF , sh , 1.433 , 1.156
#   当前价 1.433 ，参考数据价 1.156（存到备注字段 extra 或忽略）
# BASE = 10000,0.7,0.005,3,100,0.10,0.25,0.67,0.76
#   base_cash, one_grid_limit, max_slump_pct, trigger_add_point,
#   min_batch_count, minimum_buy_pct, clear_step_pct, bottom_buy_pct, interest_rate
# STEP = 0.051,0,3 , 0.025,0,2 , 0.01,0,1
#   sgrid_step_pct, sgrid_retain_count, sgrid_add_pct,
#   mgrid_step_pct, mgrid_retain_count, mgrid_add_pct,
#   lgrid_step_pct, lgrid_retain_count, lgrid_add_pct
# INTEREST = 2025,0.045,40,0.85
cur.execute("""INSERT INTO stocks (
    id, user_id, code, name, market, current_price, mode,
    base_cash, one_grid_limit, max_slump_pct, trigger_add_point,
    min_batch_count, minimum_buy_pct, clear_step_pct, bottom_buy_pct,
    interest_year, interest_rate, interest_step, interest_trigger,
    sgrid_step_pct, sgrid_retain_count, sgrid_add_pct,
    mgrid_step_pct, mgrid_retain_count, mgrid_add_pct,
    lgrid_step_pct, lgrid_retain_count, lgrid_add_pct,
    control, status
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
    1,
    1,                # user_id
    "515650",
    "消费50ETF",
    "sh",
    1.433,
    "m3",
    # BASE
    10000.0,   # base_cash
    0.7,        # one_grid_limit
    0.005,      # max_slump_pct
    3.0,        # trigger_add_point
    100,         # min_batch_count
    0.10,       # minimum_buy_pct
    0.25,       # clear_step_pct
    0.67,       # bottom_buy_pct
    # INTEREST
    2025,        # interest_year
    0.045,       # interest_rate  ← 注意：数据中 INTEREST 行是 0.045，不是 0.76
    40,          # interest_step
    0.85,        # interest_trigger
    # STEP
    0.051, 0, 3,
    0.025, 0, 2,
    0.01,  0, 1,
    "ACTIVE",
    1,
))
print("✅ 已插入 stock: 消费50ETF (515650)")

# ── 4. 插入 trades ───────────────────────────────────────
# BUY/SELL, date, grid_label, price, count
trades = [
    ("BUY",  "2024-10-18", "小网3", 1.152, 10400),
    ("SELL", "2024-11-07", "小网3", 1.213,  8200),
    ("BUY",  "2024-10-08", "小网0", 1.379,  7000),
    ("BUY",  "2024-10-08", "小网1", 1.303,  7700),
    ("BUY",  "2024-10-18", "小网2", 1.201,  8100),
    ("BUY",  "2024-11-21", "小网3", 1.156,  8900),
    ("BUY",  "2024-10-18", "中网1", 1.170, 23700),
    ("BUY",  "2024-11-22", "小网4", 1.132, 10600),
    ("SELL", "2024-12-10", "小网4", 1.218,  8700),
    ("BUY",  "2025-01-06", "小网4", 1.132, 10600),
    ("SELL", "2025-03-17", "小网4", 1.212,  8700),
    ("BUY",  "2025-04-07", "小网4", 1.127, 10600),
    ("SELL", "2025-05-14", "小网4", 1.203,  8700),
    ("BUY",  "2025-06-13", "小网4", 1.132, 10600),
    ("SELL", "2025-08-25", "小网4", 1.203,  8700),
    ("BUY",  "2025-09-22", "大网1", 1.206, 34700),
    ("BUY",  "2025-11-05", "小网4", 1.176,  9400),
    ("BUY",  "2026-03-04", "小网5", 1.119, 10300),
    ("SELL", "2026-03-17", "小网5", 1.176,  8800),
    ("BUY",  "2026-03-23", "小网5", 1.119, 10300),
]
for typ, date, label, price, count in trades:
    cur.execute(
        "INSERT INTO trades (stock_id, type, date, grid_label, price, count) "
        "VALUES (?,?,?,?,?,?)",
        (1, typ, date, label, price, count),
    )
print(f"✅ 已插入 {len(trades)} 条交易记录")

# ── 5. 插入 grid_defs（SGRID / MGRID / LGRID）────────
# 格式：类型, 标签, pct_of_base, step_pct, limit_count
# 注意：数据中 step_pct 实际上是小数（0.01=1%），需要转成小数
grid_defs = [
    # SGRID
    ("sgrid", 0,  "小网0", 1.0000, 0.01, 3),
    ("sgrid", 1,  "小网1", 0.9518, 0.06, 3),
    ("sgrid", 2,  "小网2", 0.9059, 0.06, 3),
    ("sgrid", 3,  "小网3", 0.8623, 0.11, 3),
    ("sgrid", 4,  "小网4", 0.8207, 0.11, 3),
    ("sgrid", 5,  "小网5", 0.7812, 0.16, 3),
    ("sgrid", 6,  "小网6", 0.7436, 0.16, 3),
    ("sgrid", 7,  "小网7", 0.7077, 0.21, 3),
    ("sgrid", 8,  "小网8", 0.6736, 0.21, 3),
    ("sgrid", 9,  "小网9", 0.6412, 0.26, 3),
    ("sgrid", 10, "小网10",0.6103, 0.26, 3),
    # MGRID
    ("mgrid", 1, "中网1", 0.8838, 2.01, 1.5),
    ("mgrid", 2, "中网2", 0.7601, 2.41, 1.5),
    ("mgrid", 3, "中网3", 0.6552, 2.41, 1.5),
    # LGRID
    ("lgrid", 1, "大网1", 0.8047, 3.01, 1),
    ("lgrid", 2, "大网2", 0.6412, 4.01, 1),
]
for gt, lv, label, pct, step, lim in grid_defs:
    cur.execute(
        "INSERT INTO grid_defs (stock_id, grid_type, level, label, "
        "pct_of_base, step_pct, limit_count) VALUES (?,?,?,?,?,?,?)",
        (1, gt, lv, label, pct, step, lim),
    )
print(f"✅ 已插入 {len(grid_defs)} 条网格定义")

conn.commit()

# ── 6. 验证 ─────────────────────────────────────────────
cur.execute("SELECT code, name, mode, current_price, base_cash, interest_rate FROM stocks WHERE id=1")
print("\n📦 stock =", cur.fetchone())
cur.execute("SELECT COUNT(*) FROM trades     WHERE stock_id=1")
print(f"📦 trades = {cur.fetchone()[0]} 条")
cur.execute("SELECT COUNT(*) FROM grid_defs  WHERE stock_id=1")
print(f"📦 grid_defs = {cur.fetchone()[0]} 条")

conn.close()
print("\n🎉 全部完成！")
