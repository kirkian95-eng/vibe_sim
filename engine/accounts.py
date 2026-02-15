"""
Account management and balance-sheet utilities.

Re-exports the core account types from ledger and provides higher-level
helpers for working with groups of accounts (sector aggregation, etc.).
"""

from __future__ import annotations

from .ledger import EPSILON, Account, AccountType, Ledger, is_debit_normal

__all__ = [
    "Account",
    "AccountType",
    "EPSILON",
    "is_debit_normal",
    "sector_net_worth",
    "sector_balance_sheet",
]


def sector_net_worth(ledger: Ledger, actor_ids: list[str]) -> float:
    """Net financial position of a group of actors."""
    return sum(ledger.actor_net_worth(aid) for aid in actor_ids)


def sector_balance_sheet(ledger: Ledger, actor_ids: list[str]) -> dict[str, float]:
    """Aggregate balance-sheet totals for a sector."""
    totals: dict[str, float] = {
        "assets": 0.0,
        "liabilities": 0.0,
        "equity": 0.0,
        "revenue": 0.0,
        "expense": 0.0,
    }
    for aid in actor_ids:
        bs = ledger.balance_sheet(aid)
        totals["assets"] += sum(bs["asset"].values())
        totals["liabilities"] += sum(bs["liability"].values())
        totals["equity"] += sum(bs["equity"].values())
        totals["revenue"] += sum(bs["revenue"].values())
        totals["expense"] += sum(bs["expense"].values())
    return totals
