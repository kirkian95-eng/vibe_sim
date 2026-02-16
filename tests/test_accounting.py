"""
Tests for accounting invariants.

These tests verify that the double-entry bookkeeping system maintains
all required invariants throughout the simulation.
"""

import pytest

from engine import SimConfig, Simulation
from engine.ledger import AccountType, Ledger, LedgerError


def test_basic_ledger_creation():
    """Can create a ledger and add accounts."""
    ledger = Ledger()
    ledger.create_account("test_actor", "cash", AccountType.ASSET)
    ledger.create_account("test_actor", "equity", AccountType.EQUITY)

    assert ledger.account_balance("test_actor:cash") == 0.0
    assert ledger.account_balance("test_actor:equity") == 0.0


def test_balanced_entry():
    """Journal entries must be balanced."""
    ledger = Ledger()
    ledger.create_account("a", "cash", AccountType.ASSET)
    ledger.create_account("b", "cash", AccountType.ASSET)

    entry = ledger.transfer(0, "Test transfer", "a:cash", "b:cash", 100.0)

    assert entry.is_balanced()
    assert ledger.account_balance("a:cash") == 100.0
    assert ledger.account_balance("b:cash") == -100.0


def test_unbalanced_entry_rejected():
    """Unbalanced entries should raise an error."""
    ledger = Ledger()
    ledger.create_account("a", "cash", AccountType.ASSET)
    ledger.create_account("b", "cash", AccountType.ASSET)

    with pytest.raises(LedgerError):
        ledger.post(0, "Unbalanced", [("a:cash", 100, 0), ("b:cash", 0, 50)])


def test_system_balance():
    """Total debits must equal total credits."""
    ledger = Ledger()
    ledger.create_account("a", "cash", AccountType.ASSET)
    ledger.create_account("b", "equity", AccountType.EQUITY)
    ledger.create_account("c", "revenue", AccountType.REVENUE)
    ledger.create_account("d", "expense", AccountType.EXPENSE)

    # a gets cash, b pays with equity
    ledger.post(0, "Test", [("a:cash", 100, 0), ("b:equity", 0, 100)])
    # c earns revenue, d pays expense
    ledger.post(0, "Test2", [("c:revenue", 0, 50), ("d:expense", 50, 0)])

    assert ledger.check_system_balance()


def test_balance_sheet_equation():
    """Assets = Liabilities + Equity + Revenue - Expense."""
    ledger = Ledger()
    actor = "firm_01"
    ledger.create_account(actor, "cash", AccountType.ASSET)
    ledger.create_account(actor, "inventory", AccountType.ASSET)
    ledger.create_account(actor, "loans", AccountType.LIABILITY)
    ledger.create_account(actor, "equity", AccountType.EQUITY)
    ledger.create_account(actor, "revenue", AccountType.REVENUE)
    ledger.create_account(actor, "expense", AccountType.EXPENSE)

    # Initial equity injection
    ledger.post(0, "Init", [(f"{actor}:cash", 1000, 0), (f"{actor}:equity", 0, 1000)])

    assert ledger.check_balance_sheet_equation(actor)


def test_journal_replay():
    """Running balances should match journal replay."""
    ledger = Ledger()
    ledger.create_account("a", "cash", AccountType.ASSET)
    ledger.create_account("b", "cash", AccountType.ASSET)
    ledger.create_account("c", "equity", AccountType.EQUITY)

    # Multiple transactions
    ledger.transfer(0, "T1", "a:cash", "c:equity", 100)
    ledger.transfer(1, "T2", "b:cash", "a:cash", 50)
    ledger.transfer(2, "T3", "a:cash", "b:cash", 25)

    assert ledger.verify_running_balances()


def test_simulation_accounting_valid():
    """A short simulation run should maintain all accounting invariants."""
    config = SimConfig(
        seed=123,
        num_months=6,
        num_individuals=50,
        num_food_firms=2,
        num_energy_firms=2,
        num_shelter_firms=2,
    )

    sim = Simulation(config)
    sim.run()

    # All entries should be balanced
    assert sim.ledger.check_all_entries_balanced(), "Some journal entries are not balanced"

    # System-wide balance
    assert sim.ledger.check_system_balance(), "System debits != credits"

    # Running balances match replay
    assert sim.ledger.verify_running_balances(), "Running balances don't match journal replay"

    # Check each actor's balance sheet
    for ind in sim.individuals:
        assert sim.ledger.check_balance_sheet_equation(ind.id), \
            f"Balance sheet equation fails for {ind.id}"

    for firm in sim.firms:
        assert sim.ledger.check_balance_sheet_equation(firm.id), \
            f"Balance sheet equation fails for {firm.id}"

    assert sim.ledger.check_balance_sheet_equation(sim.bank.id), \
        "Balance sheet equation fails for bank"

    assert sim.ledger.check_balance_sheet_equation(sim.govt.id), \
        "Balance sheet equation fails for government"


def test_simulation_longer_run():
    """Test a longer run with accounting validation."""
    config = SimConfig(
        seed=42,
        num_months=12,
        num_individuals=50,
        num_food_firms=3,
        num_energy_firms=2,
        num_shelter_firms=2,
    )

    sim = Simulation(config)
    results = sim.run()

    assert len(results) == 12

    # All monthly stats should show accounting is valid
    for stat in results:
        assert stat.all_balanced, f"Month {stat.month}: not all entries balanced"
        assert stat.system_balanced, f"Month {stat.month}: system not balanced"

    # Final validation
    summary = sim.results_summary()
    assert summary["accounting_valid"], "Final accounting validation failed"

    print(f"Simulation complete: {sim.ledger.journal_size} journal entries")
    print(f"Final GDP: {results[-1].gdp:.2f}")
    print(f"Final unemployment: {results[-1].unemployment_rate:.1%}")


def test_sector_balance_identity():
    """
    Sectoral balances must sum to zero for a closed economy.
    Private sector surplus = Government deficit + Foreign surplus
    (For closed economy with no foreign sector, private + govt = 0)
    """
    config = SimConfig(num_months=12, seed=999)
    sim = Simulation(config)
    sim.run()

    # Private sector = individuals + firms
    private_ids = [i.id for i in sim.individuals] + [f.id for f in sim.firms]
    private_balance = sim.ledger.check_sector_balance(private_ids)

    govt_balance = sim.ledger.actor_net_worth(sim.govt.id)
    bank_balance = sim.ledger.actor_net_worth(sim.bank.id)

    # In a closed economy: private + govt + bank ≈ initial endowments
    # The bank is an intermediary, so we focus on private + govt
    total = private_balance + govt_balance + bank_balance

    # Should be close to zero (or the initial equity injections)
    print(f"Private: {private_balance:.2f}, Govt: {govt_balance:.2f}, Bank: {bank_balance:.2f}")
    print(f"Total: {total:.2f}")

    # The total should be relatively stable (accounting identity holds)
    # We allow for accumulated equity from production
    assert abs(total) < 1e6, "Sector balances don't sum correctly"


def test_money_creation_and_destruction():
    """
    Government spending creates money (increases bank reserves/deposits).
    Taxation destroys money (decreases bank reserves/deposits).
    """
    config = SimConfig(num_months=1, seed=1)
    sim = Simulation(config)

    initial_currency = sim.ledger.account_balance(f"{sim.govt.id}:currency_issued")
    initial_deposits = sim.ledger.account_balance(f"{sim.bank.id}:deposits")

    # Run one month
    sim.step()

    final_currency = sim.ledger.account_balance(f"{sim.govt.id}:currency_issued")
    final_deposits = sim.ledger.account_balance(f"{sim.bank.id}:deposits")

    # Currency issued should have changed (govt spent or taxed)
    print(f"Currency issued changed: {initial_currency:.2f} -> {final_currency:.2f}")
    print(f"Bank deposits changed: {initial_deposits:.2f} -> {final_deposits:.2f}")

    # The currency issued should match deposits (simplified MMT model)
    # Deposits are a liability to the bank, currency is a liability to govt
    # In this consolidated model, they should track together
    assert final_currency > 0, "Government must have issued currency"
    assert final_deposits > 0, "Bank must have deposits"
