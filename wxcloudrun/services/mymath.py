"""数学工具库"""
from datetime import datetime


def align_price(price, precision=3):
    factor = 10 ** precision
    return round(price * factor) / factor


def to_percent(value):
    return f"{value * 100:.2f}%"


def to_trading_gap(buy_price, sell_price):
    if buy_price == 0:
        return "0.00%"
    return to_percent((sell_price - buy_price) / buy_price)


def proportion_pct_str(part, total):
    if total == 0:
        return "0.00%"
    return to_percent(part / total)
