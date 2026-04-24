"""
网格交易核心逻辑
支持三种模式：m1（固定步进）、m2（分段均衡）、m3（手动指定）
"""
from dataclasses import dataclass, field
from .mymath import align_price


@dataclass
class StockInfo:
    code: str
    name: str
    market: str = "sz"
    status: int = 1
    price: float = 0.0


@dataclass
class BaseParams:
    base_cash: float = 10000.0
    one_grid_limit: float = 0.67
    max_slump_pct: float = 0.2
    trigger_add_point: float = 0.005
    trading_price_precision: int = 3
    min_batch_count: int = 100
    max_rise_pct: float = 0.07
    mode: str = "m1"
    control: str = "ACTIVE"


@dataclass
class GridStepParams:
    sgrid_step_pct: float = 0.05
    sgrid_retain_count: int = 0
    sgrid_add_pct: float = 0.0
    mgrid_step_pct: float = 0.05
    mgrid_retain_count: int = 0
    mgrid_add_pct: float = 0.0
    lgrid_step_pct: float = 0.05
    lgrid_retain_count: int = 0
    lgrid_add_pct: float = 0.0


@dataclass
class TradeRecord:
    type: str
    date: str = ""
    grid_label: str = ""
    price: float = 0.0
    count: int = 0


@dataclass
class GridRow:
    level: int
    grid_type: str
    buy_price: float
    buy_count: int
    sell_price: float
    sell_count: int
    trigger_buy: bool = False
    trigger_sell: bool = False
    status: str = "monitor"
    profit_on_sell: float = 0.0
    profit_on_clear: float = 0.0


def calc_base_value(base_cash, one_grid_limit, min_batch_count, price):
    if price <= 0:
        return 0
    budget = base_cash * one_grid_limit
    raw_count = budget / price
    count = int(raw_count // min_batch_count) * min_batch_count
    return max(count, min_batch_count)


def generate_one_row(level, grid_type, base_price, step_pct, retain_count, base_params):
    buy_price = align_price(base_price * (1 - step_pct * level),
                            base_params.trading_price_precision)
    if buy_price <= 0:
        return None

    buy_count = calc_base_value(
        base_params.base_cash, base_params.one_grid_limit,
        base_params.min_batch_count, buy_price)

    sell_price = align_price(buy_price * (1 + step_pct),
                             base_params.trading_price_precision)
    sell_count = max(buy_count - retain_count, 0)

    return GridRow(
        level=level, grid_type=grid_type,
        buy_price=buy_price, buy_count=buy_count,
        sell_price=sell_price, sell_count=sell_count,
        profit_on_sell=(sell_price - buy_price) * sell_count,
        profit_on_clear=(sell_price - buy_price) * buy_count,
    )


def generate_grids(stock_info, base_params, step_params, current_price):
    grids = []
    base_price = current_price if current_price > 0 else 1.0

    for grid_type, step_pct, retain in [
        ("sgrid", step_params.sgrid_step_pct, step_params.sgrid_retain_count),
        ("mgrid", step_params.mgrid_step_pct, step_params.mgrid_retain_count),
        ("lgrid", step_params.lgrid_step_pct, step_params.lgrid_retain_count),
    ]:
        max_level = 30
        for i in range(1, max_level + 1):
            row = generate_one_row(i, grid_type, base_price, step_pct, retain, base_params)
            if row is None or row.buy_price < base_price * (1 - base_params.max_slump_pct):
                break
            grids.append(row)

    grids.sort(key=lambda g: g.buy_price)

    for g in grids:
        if current_price > 0:
            if g.buy_price >= current_price:
                g.trigger_buy = True
                g.status = "triggered"
            if g.sell_price <= current_price:
                g.trigger_sell = True
                g.status = "triggered"

    return grids


def pair_trades(records):
    pairs = []
    buy_stack = []
    for r in sorted(records, key=lambda x: x.date):
        if r.type == "BUY":
            buy_stack.append(r)
        elif r.type == "SELL" and buy_stack:
            buy = buy_stack.pop(0)
            pairs.append({
                "buy_date": buy.date, "buy_price": buy.price,
                "buy_count": buy.count, "sell_date": r.date,
                "sell_price": r.price, "sell_count": r.count,
                "profit": (r.price - buy.price) * min(buy.count, r.count),
            })
    return pairs


def calc_holding(records, current_price):
    total_buy = total_buy_count = total_sell = total_sell_count = 0
    for r in records:
        if r.type == "BUY":
            total_buy += r.price * r.count
            total_buy_count += r.count
        elif r.type == "SELL":
            total_sell += r.price * r.count
            total_sell_count += r.count
    net_count = total_buy_count - total_sell_count
    avg_cost = total_buy / total_buy_count if total_buy_count > 0 else 0
    current_value = net_count * current_price
    profit = current_value - (total_buy - total_sell)
    profit_pct = profit / (total_buy - total_sell) if (total_buy - total_sell) > 0 else 0
    return {
        "total_buy": total_buy, "total_buy_count": total_buy_count,
        "total_sell": total_sell, "total_sell_count": total_sell_count,
        "net_count": net_count, "avg_cost": round(avg_cost, 6),
        "current_value": round(current_value, 2),
        "profit": round(profit, 2), "profit_pct": round(profit_pct, 4),
    }


def run_grid_analysis(stock_info, base_params, step_params, current_price, records):
    grids = generate_grids(stock_info, base_params, step_params, current_price)
    holding = calc_holding(records, current_price)
    return {
        "stock_info": vars(stock_info), "grids": [vars(g) for g in grids],
        "holding": [holding], "total_cost": holding["total_buy"],
        "total_count": holding["net_count"], "total_value": holding["current_value"],
        "total_profit": holding["profit"], "total_profit_pct": holding["profit_pct"],
        "records": [vars(r) for r in records],
    }
