"""
网格交易核心逻辑
支持三种模式：m1（固定步进）、m2（分段均衡）、m3（手动指定）
复刻自 codes-trading-strategy (TypeScript)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from .mymath import (
    align_price, my_floor, my_ceil, fixed_price,
    to_percent, to_trading_gap, proportion_pct_str,
    to_number, is_numeric, time_duration,
    average_price_str, next_interest_date,
    n_years_ago, recent_date, get_today_str,
    calc_grid_incomes,
)


# ── 控制状态 ───
CONTROL_ACTIVE = "ACTIVE"
CONTROL_DEBUG  = "DEBUG"
CONTROL_PAUSE  = "PAUSE"
CONTROL_CLEAR  = "CLEAR"
CONTROL_CANCEL = "CANCEL"

# ── 网格类型名称 ───
SGRID_TYPE = "小网"
MGRID_TYPE = "中网"
LGRID_TYPE = "大网"
PERFIT_TYPE = "利润"


@dataclass
class StockInfo:
    code: str
    name: str
    market: str = "sz"
    status: int = 1
    price: float = 0.0


@dataclass
class BaseParams:
    """基础参数（复刻 GridTradingSettings）"""
    base_cash: float = 10000.0
    one_grid_limit: float = 1.0
    max_slump_pct: float = 0.2
    trigger_add_point: float = 0.005
    trading_price_precision: int = 3
    min_batch_count: int = 100
    max_rise_pct: float = 0.07
    mode: str = "m1"
    control: str = CONTROL_ACTIVE

    # 从源项目补充的缺失参数
    minimum_buy_pct: float = 0.1       # MINIMUM_BUY_PCT  最低买入百分比
    clear_step_pct: float = 0.25       # CLEAR_STEP_PCT  清仓步进百分比
    bottom_buy_pct: float = 0.2        # BOTTOM_BUY_PCT  底部买入百分比

    # 利息/周期性计息参数
    interest_year: int = 2025            # INTEREST_YEAR
    interest_rate: float = 0.045        # INTEREST_RATE
    interest_step: int = 40             # INTEREST_STEP
    interest_trigger: float = 0.85       # INTEREST_TRIGGER


@dataclass
class GridStepParams:
    """网格步进参数（复刻 GridTradingSettings 的步进部分）"""
    sgrid_step_pct: float = 0.05
    sgrid_retain_count: int = 0
    sgrid_add_pct: float = 0.0

    mgrid_step_pct: float = 0.05
    mgrid_retain_count: int = 0
    mgrid_add_pct: float = 0.0

    lgrid_step_pct: float = 0.05
    lgrid_retain_count: int = 0
    lgrid_add_pct: float = 0.0

    # M3 模式：手动指定的步进表（对应源项目 SGRID/MGRID/LGRID 行）
    sgrid_step_table: List[List[str]] = field(default_factory=list)
    mgrid_step_table: List[List[str]] = field(default_factory=list)
    lgrid_step_table: List[List[str]] = field(default_factory=list)


@dataclass
class TradeRecord:
    """交易记录（扩展支持 SHARE / APY / ADJ）"""
    type: str                 # BUY / SELL / SHARE / APY / ADJ / CTRL
    date: str = ""
    grid_label: str = ""
    price: float = 0.0
    count: int = 0
    extra: str = ""        # 附加信息（ADJ 的调整内容等）


@dataclass
class GridRow:
    """网格行（复刻源项目的 trading_table 行）"""
    grid_label: str = ""       # 网格标签（如 "小网0"）
    buy_pct_str: str = ""     # 价格档位（百分比字符串）
    buy_trigger: float = 0.0  # 买入触发价
    buy_price: float = 0.0
    buy_count: int = 0
    buy_cost: float = 0.0
    sell_trigger: float = 0.0  # 卖出触发价
    sell_price: float = 0.0
    sell_count: int = 0
    sell_gain: float = 0.0
    rel_downside: str = ""    # 相对跌幅
    rel_upside: str = ""      # 相对涨幅
    profit_on_sell: str = ""  # 止盈获利
    profit_on_clear: str = ""  # 清仓获利
    trigger_buy: bool = False
    trigger_sell: bool = False
    status: str = "monitor"   # monitor / triggered / disabled


# ── 基础工具函数 ─────────────────────────────────────

def calc_base_value(base_cash, one_grid_limit, min_batch_count, price):
    if not price or price <= 0:
        return 0
    budget = base_cash * one_grid_limit
    raw_count = budget / price
    count = int(raw_count // min_batch_count) * min_batch_count
    return max(count, min_batch_count)


def calc_base_value_with_add(base_cash, one_grid_limit, min_batch_count,
                            price, add_pct, idx):
    """带追加百分比的买入份数计算（复刻源项目 M1/M2/M3 的 buy_count 计算）"""
    if not price or price <= 0:
        return 0
    budget = base_cash * (1 + idx * add_pct) * one_grid_limit
    raw_count = budget / price
    count = int(raw_count // min_batch_count) * min_batch_count
    return max(count, min_batch_count)


# ── M1 模式：固定步进 ────────────────────────────────

def generate_row_m1(grid_label: str, idx: int,
                     grid_step_pct: float, retain_count: int, add_pct: float,
                     target_price: float, base_params: BaseParams,
                     precision: int) -> Optional[Dict]:
    """生成 M1 模式的一行（固定步进）"""
    buy_pct = 1.0 - grid_step_pct * idx
    if buy_pct <= 0:
        return None
    buy_price = fixed_price(target_price, buy_pct, precision)
    if buy_price <= 0:
        return None

    buy_count = calc_base_value_with_add(
        base_params.base_cash, base_params.one_grid_limit,
        base_params.min_batch_count, buy_price, add_pct, idx
    )

    sell_pct = buy_pct + grid_step_pct
    sell_price = fixed_price(target_price, sell_pct, precision)
    retain = (sell_price - buy_price) * buy_count * retain_count
    sell_count = my_floor((sell_price * buy_count - retain) / sell_price,
                          base_params.min_batch_count)

    buy_cost = ceil(buy_price * buy_count)
    sell_gain = ceil(sell_price * sell_count)

    first_income, clear_income = calc_grid_incomes(
        buy_count - sell_count,
        base_params.clear_step_pct,
        base_params.clear_step_pct,  # 简化：用同一值
    )

    return {
        "grid_label": grid_label,
        "buy_pct_str": to_percent(buy_pct, 0),
        "buy_trigger": round(buy_price + base_params.trigger_add_point, precision),
        "buy_price": buy_price,
        "buy_count": buy_count,
        "buy_cost": buy_cost,
        "sell_trigger": round(sell_price - base_params.trigger_add_point, precision),
        "sell_price": sell_price,
        "sell_count": sell_count,
        "sell_gain": sell_gain,
        "rel_downside": to_trading_gap(buy_price, sell_price),
        "rel_upside": to_trading_gap(sell_price, buy_price),
        "profit_on_sell": to_percent((first_income + sell_gain - buy_cost) / buy_cost if buy_cost else 0),
        "profit_on_clear": to_percent((clear_income + sell_gain - buy_cost) / buy_cost if buy_cost else 0),
        "trigger_buy": False,
        "trigger_sell": False,
        "status": "monitor",
    }


def generate_grids_m1(target_price: float, base_params: BaseParams,
                      step_params: GridStepParams) -> List[Dict]:
    """M1 模式：小/中/大网固定步进生成"""
    precision = base_params.trading_price_precision
    rows = []
    min_buy_price = target_price * (1 - base_params.max_slump_pct)

    for grid_type, step_pct, retain, add_pct, grid_name in [
        (step_params.sgrid_step_pct, step_params.sgrid_retain_count,
         step_params.sgrid_add_pct, SGRID_TYPE),
        (step_params.mgrid_step_pct, step_params.mgrid_retain_count,
         step_params.mgrid_add_pct, MGRID_TYPE),
        (step_params.lgrid_step_pct, step_params.lgrid_retain_count,
         step_params.lgrid_add_pct, LGRID_TYPE),
    ]:
        max_level = int(base_params.max_slump_pct / step_pct) + 1
        for i in range(0, max_level):
            label = f"{grid_name}{i}"
            row = generate_row_m1(
                label, i, step_pct, retain, add_pct,
                target_price, base_params, precision
            )
            if row is None:
                break
            if row["buy_price"] < min_buy_price:
                break
            rows.append(row)

    # 排序（按买入价格）
    rows.sort(key=lambda r: r["buy_price"])
    return rows


# ── M2 模式：分段均衡 ────────────────────────────────

def generate_row_m2(grid_label: str, idx: int,
                     buy_step_pct: float, sell_step_pct: float,
                     retain_count: int, add_pct: float,
                     target_price: float, base_params: BaseParams,
                     precision: int) -> Optional[Dict]:
    """生成 M2 模式的一行（分段均衡）"""
    if buy_step_pct <= 0:
        return None
    buy_price = fixed_price(target_price, buy_step_pct, precision)
    if buy_price <= 0:
        return None

    buy_count = calc_base_value_with_add(
        base_params.base_cash, base_params.one_grid_limit,
        base_params.min_batch_count, buy_price, add_pct, idx,
    )

    sell_price = fixed_price(target_price, sell_step_pct, precision)
    retain = (sell_price - buy_price) * buy_count * retain_count
    sell_count = my_floor((sell_price * buy_count - retain) / sell_price,
                          base_params.min_batch_count)

    buy_cost = ceil(buy_price * buy_count)
    sell_gain = ceil(sell_price * sell_count)

    first_income, clear_income = calc_grid_incomes(
        buy_count - sell_count,
        base_params.clear_step_pct,
        base_params.clear_step_pct,
    )

    return {
        "grid_label": grid_label,
        "buy_pct_str": to_percent(buy_step_pct, 0),
        "buy_trigger": round(buy_price + base_params.trigger_add_point, precision),
        "buy_price": buy_price,
        "buy_count": buy_count,
        "buy_cost": buy_cost,
        "sell_trigger": round(sell_price - base_params.trigger_add_point, precision),
        "sell_price": sell_price,
        "sell_count": sell_count,
        "sell_gain": sell_gain,
        "rel_downside": to_trading_gap(buy_price, sell_price),
        "rel_upside": to_trading_gap(sell_price, buy_price),
        "profit_on_sell": to_percent((first_income + sell_gain - buy_cost) / buy_cost if buy_cost else 0),
        "profit_on_clear": to_percent((clear_income + sell_gain - buy_cost) / buy_cost if buy_cost else 0),
        "trigger_buy": False,
        "trigger_sell": False,
        "status": "monitor",
    }


def generate_grids_m2(target_price: float, base_params: BaseParams,
                      step_params: GridStepParams) -> List[Dict]:
    """M2 模式：通过大网衰减实现小网步进均衡（复刻 grid_trading_m2.ts）"""
    precision = base_params.trading_price_precision
    lgrid_step = step_params.lgrid_step_pct
    count = int(1 - base_params.max_slump_pct) // lgrid_step + 1
    rows = []

    # 小网
    idx = 0
    max_slump_raw = round((1 - base_params.max_slump_pct) * 100)
    for i in range(0, count):
        first_step = round(100 * ((1 - lgrid_step) ** i)) / 100
        slump_pct = round(100 * ((1 - lgrid_step) ** (i + 1))) / 100
        step_pct = first_step
        ti = 1
        while step_pct > slump_pct and step_pct > max_slump_raw / 100:
            sell_step = step_pct
            row = generate_row_m2(
                f"{SGRID_TYPE}{idx}", idx, step_pct, sell_step,
                step_params.sgrid_retain_count, step_params.sgrid_add_pct,
                target_price, base_params, precision,
            )
            if row:
                rows.append(row)
            sell_step = step_pct
            step_pct = round(first_step * (1 - ti * step_params.sgrid_step_pct))
            ti += 1
            idx += 1

    # 中网
    idx = 0
    for i in range(0, count):
        first_step = round(100 * ((1 - lgrid_step) ** i)) / 100
        slump_pct = round(100 * ((1 - lgrid_step) ** (i + 1))) / 100
        step_pct = round(first_step * (1 - step_params.mgrid_step_pct))
        ti = 2
        while step_pct > slump_pct and step_pct > max_slump_raw / 100:
            sell_step = step_pct
            row = generate_row_m2(
                f"{MGRID_TYPE}{idx}", idx, step_pct, sell_step,
                step_params.mgrid_retain_count, step_params.mgrid_add_pct,
                target_price, base_params, precision,
            )
            if row:
                rows.append(row)
            sell_step = step_pct
            step_pct = round(first_step * (1 - ti * step_params.mgrid_step_pct))
            ti += 1
            idx += 1

    # 大网
    idx = 0
    for i in range(0, count):
        sell_step = round(100 * ((1 - lgrid_step) ** i)) / 100
        step_pct = round(100 * ((1 - lgrid_step) ** (i + 1))) / 100
        if step_pct > max_slump_raw / 100:
            row = generate_row_m2(
                f"{LGRID_TYPE}{idx}", idx, step_pct, sell_step,
                step_params.lgrid_retain_count, step_params.lgrid_add_pct,
                target_price, base_params, precision,
            )
            if row:
                rows.append(row)
            idx += 1

    rows.sort(key=lambda r: r["buy_price"])
    return rows


# ── M3 模式：手动指定步进 ─────────────────────────────

def generate_grids_m3(target_price: float, base_params: BaseParams,
                      step_params: GridStepParams) -> List[Dict]:
    """M3 模式：根据手动指定的 SGRID/MGRID/LGRID 行生成网格"""
    precision = base_params.trading_price_precision
    rows = []
    grid_sell_pct = 1.0 + step_params.sgrid_step_pct

    # 小网（使用 sgrid_step_table）
    for idx, entry in enumerate(step_params.sgrid_step_table):
        grid_buy_pct = to_number(entry[1]) / 100 if len(entry) > 1 else 1.0
        row = generate_row_m2(
            entry[0] if entry else f"{SGRID_TYPE}{idx}",
            idx, grid_buy_pct, grid_sell_pct,
            to_number(entry[2]) if len(entry) > 2 else 0,
            to_number(entry[3]) if len(entry) > 3 else step_params.sgrid_add_pct,
            target_price, base_params, precision,
        )
        if row:
            rows.append(row)
        grid_sell_pct = grid_buy_pct

    # 中网
    grid_sell_pct = 1.0 + step_params.mgrid_step_pct
    offset = len(step_params.sgrid_step_table)
    for idx, entry in enumerate(step_params.mgrid_step_table):
        grid_buy_pct = to_number(entry[1]) / 100 if len(entry) > 1 else 1.0
        row = generate_row_m2(
            entry[0] if entry else f"{MGRID_TYPE}{idx}",
            idx, grid_buy_pct, grid_sell_pct,
            to_number(entry[2]) if len(entry) > 2 else 0,
            to_number(entry[3]) if len(entry) > 3 else step_params.mgrid_add_pct,
            target_price, base_params, precision,
        )
        if row:
            rows.append(row)
        grid_sell_pct = grid_buy_pct

    # 大网
    grid_sell_pct = 1.0 + step_params.lgrid_step_pct
    for idx, entry in enumerate(step_params.lgrid_step_table):
        grid_buy_pct = to_number(entry[1]) / 100 if len(entry) > 1 else 1.0
        row = generate_row_m2(
            entry[0] if entry else f"{LGRID_TYPE}{idx}",
            idx, grid_buy_pct, grid_sell_pct,
            to_number(entry[2]) if len(entry) > 2 else 0,
            to_number(entry[3]) if len(entry) > 3 else step_params.lgrid_add_pct,
            target_price, base_params, precision,
        )
        if row:
            rows.append(row)
        grid_sell_pct = grid_buy_pct

    rows.sort(key=lambda r: r["buy_price"])
    return rows


# ── 主分发函数 ─────────────────────────────────────────

def generate_grids(stock_info: StockInfo, base_params: BaseParams,
                   step_params: GridStepParams, current_price: float) -> List[Dict]:
    """根据 mode 分发到 M1/M2/M3 生成网格"""
    target_price = current_price if current_price > 0 else 1.0

    if base_params.mode == "m2":
        rows = generate_grids_m2(target_price, base_params, step_params)
    elif base_params.mode == "m3":
        rows = generate_grids_m3(target_price, base_params, step_params)
    else:
        rows = generate_grids_m1(target_price, base_params, step_params)

    # 标记触发状态
    for row in rows:
        if current_price > 0:
            if row["buy_price"] >= current_price:
                row["trigger_buy"] = True
                row["status"] = "triggered"
            if row["sell_price"] <= current_price:
                row["trigger_sell"] = True
                row["status"] = "triggered"

    return rows


# ── 交易记录分析 ───────────────────────────────────────

def pair_trades(records: List[TradeRecord]) -> List[Dict]:
    """配对 BUY/SELL 记录（复刻 InitTradingRecord 的配对逻辑）"""
    pairs = []
    buy_stack = []
    for r in sorted(records, key=lambda x: x.date):
        if r.type == "BUY":
            buy_stack.append(r)
        elif r.type == "SELL" and buy_stack:
            buy = buy_stack.pop(0)
            pairs.append({
                "buy_date": buy.date,
                "buy_price": buy.price,
                "buy_count": buy.count,
                "sell_date": r.date,
                "sell_price": r.price,
                "sell_count": r.count,
                "profit": (r.price - buy.price) * min(buy.count, r.count),
                "cost_count": ceil(buy.price * buy.count - r.price * r.count),
                "hold_days": time_duration(buy.date, r.date),
                "retain_count": max(buy.count - r.count, 0),
            })
    return pairs


def calc_holding(records: List[TradeRecord], current_price: float) -> Dict:
    """计算持仓分析（复刻 calc_holding）"""
    total_buy = total_buy_count = total_sell = total_sell_count = 0
    retain_total = 0
    retain_cost = 0

    for r in records:
        if r.type == "BUY":
            total_buy += r.price * r.count
            total_buy_count += r.count
        elif r.type == "SELL":
            total_sell += r.price * r.count
            total_sell_count += r.count
        elif r.type == "SHARE" and r.grid_label == "红利":
            # 红利再投：减少占用本金
            gain_cost = ceil(r.price * r.count)
            retain_cost -= gain_cost
        elif r.type == "SHARE" and r.grid_label == "拆股":
            retain_total += r.count

    net_count = total_buy_count - total_sell_count
    avg_cost = total_buy / total_buy_count if total_buy_count > 0 else 0
    current_value = net_count * current_price
    profit = current_value - (total_buy - total_sell)
    profit_pct = profit / (total_buy - total_sell) if (total_buy - total_sell) > 0 else 0

    return {
        "total_buy": total_buy,
        "total_buy_count": total_buy_count,
        "total_sell": total_sell,
        "total_sell_count": total_sell_count,
        "net_count": net_count,
        "avg_cost": round(avg_cost, 6),
        "current_value": round(current_value, 2),
        "profit": round(profit, 2),
        "profit_pct": round(profit_pct, 4),
        "retain_total": retain_total,
        "retain_cost": retain_cost,
    }


# ── 主分析入口 ─────────────────────────────────────────

def run_grid_analysis(stock_info: StockInfo, base_params: BaseParams,
                     step_params: GridStepParams, current_price: float,
                     records: List[TradeRecord]) -> Dict:
    """主分析入口（复刻 GridTrading.InitGridTrading）"""
    grids = generate_grids(stock_info, base_params, step_params, current_price)
    holding = calc_holding(records, current_price)
    pairs = pair_trades(records)

    # 计算清仓/止盈价格
    clear_price_1 = fixed_price(target_price=current_price,
                                 step_pct=1.0 + base_params.clear_step_pct,
                                 precision=base_params.trading_price_precision)
    clear_avg_price = clear_price_1  # 简化

    return {
        "stock_info": vars(stock_info),
        "base_params": vars(base_params),
        "step_params": vars(step_params),
        "grids": grids,
        "holding": holding,
        "pairs": pairs,
        "total_cost": holding["total_buy"],
        "total_count": holding["net_count"],
        "total_value": holding["current_value"],
        "total_profit": holding["profit"],
        "total_profit_pct": holding["profit_pct"],
        "clear_price": round(clear_price_1, base_params.trading_price_precision),
        "clear_avg_price": round(clear_avg_price, base_params.trading_price_precision),
        "records": [vars(r) for r in records],
        "control": base_params.control,
        "is_debug": base_params.control == CONTROL_DEBUG,
        "is_pause": base_params.control == CONTROL_PAUSE,
        "is_clear": base_params.control == CONTROL_CLEAR,
        "is_cancel": base_params.control == CONTROL_CANCEL,
    }
