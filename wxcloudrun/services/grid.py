"""
网格交易核心算法
- M1: 简化固定步进（向后兼容）
- M2: 分段均衡（预留）
- M3: 从 grid_defs 表读取手动指定网格
"""
from typing import List, Dict


# ── 数据结构 ───────────────────────────────

class StockInfo:
    def __init__(self, code, name, market, price):
        self.code = code
        self.name = name
        self.market = market
        self.price = price


class BaseParams:
    def __init__(self, **kwargs):
        self.base_cash = kwargs.get('base_cash', 10000)
        self.mode = kwargs.get('mode', 'm1')
        self.one_grid_limit = kwargs.get('one_grid_limit', 3.0)
        self.max_slump_pct = kwargs.get('max_slump_pct', 0.0)


class GridStepParams:
    def __init__(self, **kwargs):
        self.sgrid_step_pct = kwargs.get('sgrid_step_pct', 0.03)
        self.mgrid_step_pct = kwargs.get('mgrid_step_pct', 0.05)
        self.lgrid_step_pct = kwargs.get('lgrid_step_pct', 0.05)


# ── 内部工具 ─────────────────────────────

def _make_grid_entry(grid_type: str, level: int, buy_price: float,
                    sell_price: float, buy_count: int,
                    current_price: float) -> Dict:
    """生成单条网格 dict"""
    return {
        'grid_type':       grid_type,
        'level':           level,
        'buy_price':      round(buy_price, 3),
        'buy_count':       buy_count,
        'sell_price':     round(sell_price, 3),
        'sell_count':      max(100, int(buy_count * 0.5) // 100 * 100),
        'trigger_buy':    current_price <= buy_price,
        'trigger_sell':   current_price >= sell_price,
        'profit_on_sell': round((sell_price - buy_price) * buy_count, 2),
        'profit_on_clear': round((sell_price - buy_price) * max(1, buy_count // 2), 2),
    }


def _calc_holding(records: List[Dict]) -> Dict:
    """根据交易记录计算持仓"""
    total_buy = 0.0
    total_sell = 0.0
    net_count = 0
    buy_count_total = 0
    sell_count_total = 0

    for r in records:
        if r['type'] == 'BUY':
            total_buy += r['price'] * r['count']
            net_count += r['count']
            buy_count_total += r['count']
        else:
            total_sell += r['price'] * r['count']
            net_count -= r['count']
            sell_count_total += r['count']

    avg_cost = round(total_buy / net_count, 3) if net_count > 0 else 0.0
    return {
        'net_count':       net_count,
        'avg_cost':        avg_cost,
        'market_value':    round(net_count * 0.0, 3),  # 由调用方填入 current_price
        'profit':          0.0,  # 由调用方计算
        'profit_pct':     0.0,
        'total_buy_count':  buy_count_total,
        'total_sell_count': sell_count_total,
    }


# ── M1：简化固定步进 ──────────────────────

def _generate_m1(current_price: float, base_params: BaseParams,
                 step_params: GridStepParams) -> List[Dict]:
    grids = []
    precision = 3
    for i in range(5):
        buy_price = round(current_price * (1 - step_params.sgrid_step_pct * (i + 1)), precision)
        sell_price = round(buy_price * (1 + step_params.sgrid_step_pct), precision)
        buy_count = max(100, int(base_params.base_cash * 0.3 / buy_price / 100) * 100)
        grids.append(_make_grid_entry('sgrid', i, buy_price, sell_price, buy_count, current_price))
    return grids


# ── M3：从 grid_defs 读取 ─────────────────

def _generate_m3(current_price: float, base_params: BaseParams,
                  grid_defs: List[Dict]) -> List[Dict]:
    """
    grid_defs: 来自 dao.get_grid_defs() 的列表，每条含
        grid_type, level, label, pct_of_base, step_pct, limit_count
    买入价 = current_price × pct_of_base
    卖出价 = 买入价 × (1 + step_pct)
    买入数量根据 base_cash 和 limit_count 计算
    """
    grids = []
    base_cash = base_params.base_cash
    one_grid_limit = base_params.one_grid_limit  # 单网格资金上限（万元）或股数倍率

    for gd in grid_defs:
        gt = gd['grid_type']          # 'sgrid' / 'mgrid' / 'lgrid'
        lv = gd['level']
        pct = gd['pct_of_base']     # 如 0.9518 = 95.18%
        step = gd['step_pct']        # 如 0.06 = 6%
        lim = gd['limit_count']      # 如 3.0

        buy_price = round(current_price * pct, 3)
        sell_price = round(buy_price * (1 + step), 3)

        # 买入数量：用 base_cash 的一部分除以买入价
        # lim 在此作为"单网格最大股数倍率"使用（与原项目对齐）
        raw_count = int(base_cash * 0.3 / buy_price / 100) * 100
        buy_count = max(100, int(raw_count * lim)) if lim else raw_count

        grids.append(_make_grid_entry(gt, lv, buy_price, sell_price, buy_count, current_price))

    return grids


# ── 主入口 ─────────────────────────────────

def run_grid_analysis(stock_info, base_params, step_params,
                      current_price, records, grid_defs=None):
    """
    grid_defs: 仅 M3 模式需要，来自 dao.get_grid_defs()
    """
    try:
        # ── 生成网格 ──
        if base_params.mode == 'm3' and grid_defs:
            grids = _generate_m3(current_price, base_params, grid_defs)
        else:
            # M1 / M2 走简化逻辑
            grids = _generate_m1(current_price, base_params, step_params)

        # ── 计算持仓 ──
        holding = _calc_holding(records)
        h = holding
        h['market_value'] = round(h['net_count'] * current_price, 2)
        h['profit'] = round(h['net_count'] * current_price - (h['avg_cost'] * h['net_count'] if h['net_count'] > 0 else 0), 2)
        h['profit_pct'] = round(h['profit'] / (h['avg_cost'] * h['net_count']), 4) if h['avg_cost'] > 0 else 0.0

        total_cost = sum(r['price'] * r['count'] for r in records if r['type'] == 'BUY')
        total_value = h['net_count'] * current_price

        return {
            'grids':       grids,
            'holding':    [h],
            'records':    records,
            'total_cost':  round(total_cost, 2),
            'total_value': round(total_value, 2),
            'total_profit': round(total_value - total_cost, 2),
        }

    except Exception as e:
        print(f"[grid.py] run_grid_analysis error: {e}")
        return {
            'grids':       [],
            'holding':     [{'net_count': 0, 'avg_cost': 0, 'market_value': 0,
                           'profit': 0, 'profit_pct': 0,
                           'total_buy_count': 0, 'total_sell_count': 0}],
            'records':    records,
            'total_cost':  0,
            'total_value': 0,
            'total_profit': 0,
        }
