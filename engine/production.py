"""
Production functions and firm operational logic.

Firms produce goods using labor and capital via a Cobb-Douglas-style
production function:  output = productivity * labor^alpha * capital^beta
"""

from __future__ import annotations


def cobb_douglas(
    productivity: float,
    labor: float,
    capital: float,
    labor_share: float = 0.7,
    capital_share: float = 0.3,
) -> float:
    """
    Standard Cobb-Douglas production.

    Returns 0 if labor or capital is zero (can't produce without inputs).
    """
    if labor <= 0 or capital <= 0:
        return 0.0
    return float(productivity * (labor ** labor_share) * (capital ** capital_share))


def desired_labor(
    target_output: float,
    productivity: float,
    capital: float,
    labor_share: float = 0.7,
    capital_share: float = 0.3,
) -> float:
    """How much labor is needed to produce target_output given capital."""
    if productivity <= 0 or capital <= 0 or target_output <= 0:
        return 0.0
    capital_factor = productivity * (capital ** capital_share)
    if capital_factor <= 0:
        return 0.0
    raw = target_output / capital_factor
    return float(raw ** (1.0 / labor_share))


def firm_target_output(
    current_inventory: float,
    avg_monthly_sales: float,
    target_inventory_months: float,
) -> float:
    """
    Firms target enough inventory to cover target_inventory_months of sales,
    producing the shortfall. Always produce at least replacement (avg_sales)
    unless inventory is massively in excess (>2x target), to avoid hiring
    collapse and wage spiral when drawing down a glut.
    """
    target_inventory = avg_monthly_sales * target_inventory_months
    shortfall = target_inventory - current_inventory
    target = avg_monthly_sales + shortfall * 0.2
    ratio = current_inventory / target_inventory if target_inventory > 0 else 0
    # When near or below target, always replace sales. Only allow draw-down when glut > 2x.
    floor = 0.0 if ratio >= 2.0 else avg_monthly_sales
    return max(floor, target)


def adjust_price(
    current_price: float,
    current_inventory: float,
    avg_monthly_sales: float,
    target_inventory_months: float,
    adjustment_speed: float,
    min_price: float = 0.5,
) -> float:
    """
    If inventory is above target, lower price; if below, raise price.
    """
    if avg_monthly_sales <= 0:
        return current_price

    target_inv = avg_monthly_sales * target_inventory_months
    if target_inv <= 0:
        return current_price

    ratio = current_inventory / target_inv  # >1 means excess inventory
    # adjustment factor: negative when inventory is high, positive when low
    adj = (1.0 - ratio) * adjustment_speed
    # Cap per-month adjustment to +/-speed to prevent compound spiraling
    adj = max(-adjustment_speed, min(adj, adjustment_speed))
    new_price = current_price * (1.0 + adj)
    return max(min_price, new_price)


def adjust_wage(
    current_wage: float,
    unemployment_rate: float,
    adjustment_speed: float,
    target_unemployment: float = 0.05,
    min_wage: float = 20.0,
) -> float:
    """
    Phillips-curve-style wage adjustment per month.
    Low unemployment -> wages rise. High unemployment -> wages fall.
    """
    gap = target_unemployment - unemployment_rate  # negative when unemployment exceeds target
    adj = gap * adjustment_speed  # wages rise when gap > 0 (low unemployment)
    new_wage = current_wage * (1.0 + adj)
    return max(min_wage, new_wage)
