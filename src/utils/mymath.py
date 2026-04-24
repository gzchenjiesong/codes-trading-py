"""数学工具库 — 从 TypeScript mymath.ts 移植"""
from datetime import datetime


def fixed_price(price: float, pct: float) -> float:
    """按百分位计算价格并截断到指定精度"""
    return round(price * (1 + pct), 6)


def align_price(price: float, precision: int = 3) -> float:
    """对齐价格精度"""
    factor = 10 ** precision
    return round(price * factor) / factor


def my_floor(value: float, step: float) -> float:
    """按步进取整（向下）"""
    if step == 0:
        return value
    return int(value / step) * step


def my_ceil(value: float, step: float) -> float:
    """按步进取整（向上）"""
    if step == 0:
        return value
    import math
    return math.ceil(value / step) * step


def to_percent(value: float) -> str:
    """数值转百分比字符串"""
    return f"{value * 100:.2f}%"


def to_number(s: str) -> float:
    """字符串转数字，失败返回 0"""
    try:
        return float(s.replace(",", "").replace("%", ""))
    except (ValueError, AttributeError):
        return 0.0


def to_trading_gap(buy_price: float, sell_price: float) -> str:
    """计算价差百分比"""
    if buy_price == 0:
        return "0.00%"
    gap = (sell_price - buy_price) / buy_price
    return to_percent(gap)


def time_duration(start: str, end: str) -> int:
    """计算日期差（天数）"""
    try:
        d1 = datetime.strptime(start, "%Y-%m-%d")
        d2 = datetime.strptime(end, "%Y-%m-%d")
        return (d2 - d1).days
    except ValueError:
        return 0


def proportion_pct_str(part: float, total: float) -> str:
    """占比计算"""
    if total == 0:
        return "0.00%"
    return to_percent(part / total)
