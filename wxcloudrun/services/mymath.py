"""数学工具库 - 复刻自 codes-trading-strategy/src/mymath.ts"""
from datetime import datetime, timedelta
from math import floor, ceil


def align_price(price, precision=3):
    """价格精度对齐"""
    if not price or price <= 0:
        return 0.0
    factor = 10 ** precision
    return round(price * factor) / factor


def my_floor(n, batch):
    """向下取整到 batch 的整数倍（复刻 MyFloor）"""
    if not n or batch <= 0:
        return int(floor(n)) if n else 0
    return int(floor(n / batch)) * batch


def my_ceil(n, batch):
    """向上取整到 batch 的整数倍（复刻 MyCeil）"""
    if not n or batch <= 0:
        return int(ceil(n)) if n else 0
    return int(ceil(n / batch)) * batch


def fixed_price(base_price, step_pct, precision):
    """将价格按照 step_pct 对齐（复刻 FixedPrice）"""
    raw = base_price * step_pct
    return align_price(raw, precision)


def to_percent(value, decimals=2):
    """将小数转为百分比字符串（复刻 ToPercent）"""
    if value is None:
        return "0.00%"
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def to_trading_gap(buy_price, sell_price):
    """计算涨跌幅 (sell - buy) / buy（复刻 ToTradingGap）"""
    if not buy_price or float(buy_price) == 0:
        return "0.00%"
    try:
        gap = (float(sell_price) - float(buy_price)) / float(buy_price)
        return to_percent(gap)
    except (ValueError, TypeError, ZeroDivisionError):
        return "0.00%"


def proportion_pct_str(part, total, decimals=2):
    """计算占比字符串（复刻 ProportionPctStr）"""
    if not total or float(total) == 0:
        return "0.00%"
    try:
        return to_percent(float(part) / float(total), decimals)
    except (ValueError, TypeError, ZeroDivisionError):
        return "0.00%"


def to_number(s):
    """将字符串转为数字，失败返回 0（复刻 ToNumber）"""
    if s is None:
        return 0
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def is_numeric(s):
    """判断是否为数字字符串（复刻 IsNumeric）"""
    if s is None:
        return False
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def time_duration(start_date_str, end_date_str):
    """计算两个日期之间的天数（复刻 TimeDuration）"""
    try:
        fmt = "%Y-%m-%d"
        start = datetime.strptime(str(start_date_str)[:10], fmt)
        end = datetime.strptime(str(end_date_str)[:10], fmt)
        return abs((end - start).days)
    except (ValueError, TypeError):
        return 0


def average_price_str(cost, count, precision):
    """计算平均价格并格式化（复刻 AveragePriceStr）"""
    if not count or float(count) == 0:
        return "0." + "0" * precision
    try:
        avg = float(cost) / float(count)
        return f"{avg:.{precision}f}"
    except (ValueError, TypeError, ZeroDivisionError):
        return "0." + "0" * precision


def next_interest_date(year, record_count):
    """计算下一个计息日期（每年3月1日起递增，复刻 NextInterestDate）"""
    try:
        base_month = 3
        base_day = 1
        month = base_month
        day = base_day + int(record_count)
        while day > 28:
            month += 1
            day -= 28
        y = int(year)
        if month > 12:
            y += 1
            month -= 12
        return f"{y}-{month:02d}-{day:02d}"
    except (ValueError, TypeError):
        return f"{year}-03-01"


def n_years_ago(date_str, n):
    """计算 n 年前的日期（复刻 nYearsAgo）"""
    try:
        fmt = "%Y-%m-%d"
        d = datetime.strptime(str(date_str)[:10], fmt)
        try:
            result = d.replace(year=d.year - n)
        except ValueError:
            # 处理闰年 2月29日的情况
            result = d.replace(year=d.year - n, day=28)
        return result.strftime(fmt)
    except (ValueError, TypeError):
        return str(date_str) if date_str else ""


def recent_date(date_str, calculated_date_str):
    """取两个日期中较近的一个（复刻 RecentDate）"""
    try:
        fmt = "%Y-%m-%d"
        d1 = datetime.strptime(str(date_str)[:10], fmt)
        d2 = datetime.strptime(str(calculated_date_str)[:10], fmt)
        return max(d1, d2).strftime(fmt)
    except (ValueError, TypeError):
        return str(date_str) if date_str else ""


def get_today_str():
    """获取今日日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def calc_grid_incomes(retain_count, clear_price_1, clear_price_avg):
    """计算网格止盈和清仓收益（复刻 CalcGridIncomes）
    retain_count: 保留份数
    clear_price_1: 止盈清仓价格
    clear_price_avg: 平均清仓价格
    返回: (first_income, clear_income)
    """
    if not retain_count:
        return 0, 0
    first_income = retain_count * clear_price_1
    clear_income = retain_count * clear_price_avg
    return first_income, clear_income
