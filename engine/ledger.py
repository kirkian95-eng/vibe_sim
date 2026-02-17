"""
Append-only double-entry bookkeeping journal and ledger.

Every transaction in the simulation flows through this module.
A JournalEntry is a balanced set of debit/credit lines referencing accounts.
Account balances are maintained incrementally for performance, but the
journal is the authoritative source of truth and can be replayed.
"""

from __future__ import annotations

import dataclasses as dc
from enum import Enum

# Tolerance for floating-point balance checks (sub-cent)
EPSILON = 1e-6


class AccountType(Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


def is_debit_normal(account_type: AccountType) -> bool:
    """Assets and expenses increase with debits."""
    return account_type in (AccountType.ASSET, AccountType.EXPENSE)


@dc.dataclass
class Account:
    """A single ledger account belonging to an actor."""

    id: str  # globally unique: "{actor_id}:{account_name}"
    actor_id: str
    name: str
    account_type: AccountType
    _balance: float = dc.field(default=0.0, repr=False)

    @property
    def balance(self) -> float:
        """Positive means normal-side balance."""
        return self._balance

    def apply_debit(self, amount: float) -> None:
        if is_debit_normal(self.account_type):
            self._balance += amount
        else:
            self._balance -= amount

    def apply_credit(self, amount: float) -> None:
        if is_debit_normal(self.account_type):
            self._balance -= amount
        else:
            self._balance += amount


@dc.dataclass
class JournalLine:
    """One line of a journal entry."""

    account_id: str
    debit: float = 0.0
    credit: float = 0.0

    def __post_init__(self):
        if self.debit < -EPSILON or self.credit < -EPSILON:
            raise ValueError(f"Negative amounts not allowed: dr={self.debit} cr={self.credit}")
        if self.debit > EPSILON and self.credit > EPSILON:
            raise ValueError("A line cannot have both debit and credit")


@dc.dataclass
class JournalEntry:
    """An immutable, balanced journal entry."""

    entry_id: int
    day: int
    description: str
    lines: tuple[JournalLine, ...]
    metadata: dict | None = None

    def total_debits(self) -> float:
        return sum(ln.debit for ln in self.lines)

    def total_credits(self) -> float:
        return sum(ln.credit for ln in self.lines)

    def is_balanced(self) -> bool:
        return abs(self.total_debits() - self.total_credits()) < EPSILON


class LedgerError(Exception):
    pass


class Ledger:
    """
    Central ledger for the entire simulation economy.

    Owns the append-only journal and all accounts. Provides posting,
    balance queries, and invariant checks.
    """

    def __init__(self):
        self._accounts: dict[str, Account] = {}
        self._actor_accounts: dict[str, list[Account]] = {}  # actor_id -> accounts
        self._journal: list[JournalEntry] = []
        self._next_entry_id: int = 1

    # ── Account management ──────────────────────────────────────────

    def create_account(
        self, actor_id: str, name: str, account_type: AccountType
    ) -> Account:
        account_id = f"{actor_id}:{name}"
        if account_id in self._accounts:
            raise LedgerError(f"Account already exists: {account_id}")
        acct = Account(
            id=account_id,
            actor_id=actor_id,
            name=name,
            account_type=account_type,
        )
        self._accounts[account_id] = acct
        if actor_id not in self._actor_accounts:
            self._actor_accounts[actor_id] = []
        self._actor_accounts[actor_id].append(acct)
        return acct

    def get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as err:
            raise LedgerError(f"Account not found: {account_id}") from err

    def account_balance(self, account_id: str) -> float:
        return self.get_account(account_id).balance

    def actor_accounts(self, actor_id: str) -> list[Account]:
        return self._actor_accounts.get(actor_id, [])

    # ── Journal posting ─────────────────────────────────────────────

    def post(
        self,
        day: int,
        description: str,
        lines: list[tuple[str, float, float]],
        metadata: dict | None = None,
    ) -> JournalEntry:
        """
        Post a balanced journal entry.

        lines: list of (account_id, debit_amount, credit_amount)
        Raises LedgerError if the entry is not balanced or references
        unknown accounts.
        """
        jlines = []
        for acct_id, dr, cr in lines:
            if acct_id not in self._accounts:
                raise LedgerError(f"Unknown account: {acct_id}")
            jlines.append(JournalLine(account_id=acct_id, debit=dr, credit=cr))

        entry = JournalEntry(
            entry_id=self._next_entry_id,
            day=day,
            description=description,
            lines=tuple(jlines),
            metadata=metadata,
        )

        if not entry.is_balanced():
            raise LedgerError(
                f"Unbalanced entry #{entry.entry_id}: "
                f"debits={entry.total_debits():.4f} "
                f"credits={entry.total_credits():.4f} "
                f"desc='{description}'"
            )

        # Apply to running balances
        for line in entry.lines:
            acct = self._accounts[line.account_id]
            if line.debit > 0:
                acct.apply_debit(line.debit)
            if line.credit > 0:
                acct.apply_credit(line.credit)

        self._journal.append(entry)
        self._next_entry_id += 1
        return entry

    # ── Convenience posting helpers ─────────────────────────────────

    def transfer(
        self,
        day: int,
        description: str,
        debit_account: str,
        credit_account: str,
        amount: float,
        metadata: dict | None = None,
    ) -> JournalEntry:
        """Simple two-line entry: debit one account, credit another."""
        if amount <= 0:
            raise LedgerError(f"Transfer amount must be positive: {amount}")
        return self.post(
            day, description, [(debit_account, amount, 0), (credit_account, 0, amount)], metadata
        )

    # ── Queries ─────────────────────────────────────────────────────

    @property
    def journal(self) -> list[JournalEntry]:
        return list(self._journal)

    @property
    def journal_size(self) -> int:
        return len(self._journal)

    def entries_for_day(self, day: int) -> list[JournalEntry]:
        return [e for e in self._journal if e.day == day]

    def entries_for_account(self, account_id: str) -> list[JournalEntry]:
        return [
            e
            for e in self._journal
            if any(ln.account_id == account_id for ln in e.lines)
        ]

    # ── Balance sheet for an actor ──────────────────────────────────

    def balance_sheet(self, actor_id: str) -> dict:
        """
        Returns {assets, liabilities, equity, revenue, expense}
        where each is a dict of account_name -> balance.
        """
        result: dict[str, dict[str, float]] = {t.value: {} for t in AccountType}
        for acct in self.actor_accounts(actor_id):
            result[acct.account_type.value][acct.name] = acct.balance
        return result

    def actor_net_worth(self, actor_id: str) -> float:
        """Assets - Liabilities (equity + retained income)."""
        bs = self.balance_sheet(actor_id)
        total_assets = sum(bs["asset"].values())
        total_liabilities = sum(bs["liability"].values())
        return float(total_assets - total_liabilities)

    # ── Invariant checks ────────────────────────────────────────────

    def check_all_entries_balanced(self) -> bool:
        return all(entry.is_balanced() for entry in self._journal)

    def check_entries_balanced_from(self, start_idx: int) -> bool:
        """Check balance only for entries from start_idx onward (fast incremental check)."""
        return all(self._journal[i].is_balanced() for i in range(start_idx, len(self._journal)))

    def check_balance_sheet_equation(self, actor_id: str) -> bool:
        """Assets = Liabilities + Equity + Revenue - Expense.

        Tolerance scales with journal size to handle float64 accumulation.
        """
        bs = self.balance_sheet(actor_id)
        total_assets = sum(bs["asset"].values())
        total_liabilities = sum(bs["liability"].values())
        total_equity = sum(bs["equity"].values())
        total_revenue = sum(bs["revenue"].values())
        total_expense = sum(bs["expense"].values())
        lhs = total_assets
        rhs = total_liabilities + total_equity + total_revenue - total_expense
        tol = EPSILON + len(self._journal) * 1e-10
        return bool(abs(lhs - rhs) < tol)

    def check_system_balance(self) -> bool:
        """
        Total debits in all accounts must equal total credits.
        Equivalently: sum of all debit-normal balances = sum of all credit-normal balances.

        Uses a tolerance that scales with the number of journal entries
        to account for float64 accumulation error in large simulations.
        """
        total_debit_normal = 0.0
        total_credit_normal = 0.0
        for acct in self._accounts.values():
            if is_debit_normal(acct.account_type):
                total_debit_normal += acct.balance
            else:
                total_credit_normal += acct.balance
        # Scale tolerance: base EPSILON + 1e-10 per journal entry
        tol = EPSILON + len(self._journal) * 1e-10
        return abs(total_debit_normal - total_credit_normal) < tol

    def check_sector_balance(self, actor_ids: list[str]) -> float:
        """
        Net financial position of a sector (group of actors).
        For the whole economy this should be zero (one entity's asset
        is another's liability).
        """
        total = 0.0
        for aid in actor_ids:
            total += self.actor_net_worth(aid)
        return total

    def replay_balances(self) -> dict[str, float]:
        """
        Replay journal from scratch and return computed balances.
        Useful for auditing that running balances match the journal.
        """
        replayed: dict[str, float] = {aid: 0.0 for aid in self._accounts}
        for entry in self._journal:
            for line in entry.lines:
                acct = self._accounts[line.account_id]
                if is_debit_normal(acct.account_type):
                    replayed[line.account_id] = (
                        replayed.get(line.account_id, 0.0)
                        + line.debit
                        - line.credit
                    )
                else:
                    replayed[line.account_id] = (
                        replayed.get(line.account_id, 0.0)
                        + line.credit
                        - line.debit
                    )
        return replayed

    def verify_running_balances(self) -> bool:
        """Check that running balances match a full journal replay."""
        replayed = self.replay_balances()
        for acct_id, acct in self._accounts.items():
            if abs(acct.balance - replayed.get(acct_id, 0.0)) > EPSILON:
                return False
        return True
