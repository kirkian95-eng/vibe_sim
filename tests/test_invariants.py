"""
Strict accounting invariant tests.

These are the "hard" correctness checks:
  a) Every journal entry balances (sum debits == sum credits)
  b) Each actor's balance sheet balances (A == L + E + R - X)
  c) Consolidated sector check: changes in net financial assets
     match government deficit/surplus under our model
"""


from engine import SimConfig, Simulation
from engine.ledger import EPSILON

# ── (a) Journal entries always balance ──────────────────────────────


class TestJournalBalance:
    """Every posted entry must have debits == credits."""

    def test_every_entry_balanced_short_run(self, small_sim):
        for entry in small_sim.ledger.journal:
            assert entry.is_balanced(), (
                f"Entry #{entry.entry_id} day {entry.day} unbalanced: "
                f"dr={entry.total_debits():.6f} cr={entry.total_credits():.6f} "
                f"desc='{entry.description}'"
            )

    def test_every_entry_balanced_full_year(self):
        sim = Simulation(SimConfig(seed=77, num_days=365, num_individuals=200))
        sim.run()
        unbalanced = [
            e for e in sim.ledger.journal if not e.is_balanced()
        ]
        assert unbalanced == [], (
            f"{len(unbalanced)} unbalanced entries found"
        )

    def test_replay_matches_running_balances(self, small_sim):
        assert small_sim.ledger.verify_running_balances()

    def test_replay_matches_running_full_year(self):
        sim = Simulation(SimConfig(seed=88, num_days=365, num_individuals=200))
        sim.run()
        assert sim.ledger.verify_running_balances()


# ── (b) Balance sheet equation per actor ────────────────────────────


class TestBalanceSheetEquation:
    """Assets == Liabilities + Equity + Revenue - Expense for every actor."""

    def test_all_individuals(self, small_sim):
        for ind in small_sim.individuals:
            assert small_sim.ledger.check_balance_sheet_equation(ind.id), (
                f"Balance sheet fails for {ind.id}"
            )

    def test_all_firms(self, small_sim):
        for firm in small_sim.firms:
            assert small_sim.ledger.check_balance_sheet_equation(firm.id), (
                f"Balance sheet fails for {firm.id}"
            )

    def test_bank(self, small_sim):
        assert small_sim.ledger.check_balance_sheet_equation(small_sim.bank.id)

    def test_government(self, small_sim):
        assert small_sim.ledger.check_balance_sheet_equation(small_sim.govt.id)

    def test_system_wide_balance(self, small_sim):
        assert small_sim.ledger.check_system_balance()

    def test_balance_sheet_holds_after_365_days(self):
        sim = Simulation(SimConfig(seed=99, num_days=365, num_individuals=300))
        sim.run()
        for ind in sim.individuals:
            assert sim.ledger.check_balance_sheet_equation(ind.id)
        for firm in sim.firms:
            assert sim.ledger.check_balance_sheet_equation(firm.id)
        assert sim.ledger.check_balance_sheet_equation(sim.bank.id)
        assert sim.ledger.check_balance_sheet_equation(sim.govt.id)
        assert sim.ledger.check_system_balance()


# ── (c) Sector balance / government deficit identity ────────────────


class TestSectorBalances:
    """
    In our closed-economy model with consolidated government:
    - Government deficit creates private sector net financial assets
    - The change in private+bank net worth should equal the cumulative govt deficit
    - Total sector balances should reflect production equity only
    """

    def test_money_creation_matches_currency_issued(self):
        """Bank deposits should equal government currency_issued."""
        sim = Simulation(SimConfig(seed=42, num_days=90))
        sim.run()
        reserves = sim.ledger.account_balance(f"{sim.bank.id}:reserves")
        currency = sim.ledger.account_balance(f"{sim.govt.id}:currency_issued")

        # Reserves should equal currency issued (all money flows through bank)
        assert abs(reserves - currency) < EPSILON * 1000, (
            f"Reserves {reserves:.2f} != currency_issued {currency:.2f}"
        )

    def test_govt_net_spending_equals_currency_outstanding(self):
        """Government net spending (expense - revenue) should equal currency_issued."""
        sim = Simulation(SimConfig(seed=42, num_days=90))
        sim.run()

        # Government balance sheet
        bs = sim.ledger.balance_sheet(sim.govt.id)
        total_expense = sum(bs["expense"].values())
        total_revenue = sum(bs["revenue"].values())
        net_spending = total_expense - total_revenue

        # Currency issued is the govt's liability = total money created
        currency_issued = sim.ledger.account_balance(
            f"{sim.govt.id}:currency_issued"
        )

        # Net spending should equal outstanding currency
        # (expense - revenue = currency_issued, because each spend
        #  creates currency and each tax destroys it)
        assert abs(net_spending - currency_issued) < EPSILON * 10000, (
            f"Net spending {net_spending:.2f} != "
            f"currency_issued {currency_issued:.2f}"
        )

    def test_system_balance_holds_every_day(self):
        """System balance should hold at end of every day."""
        sim = Simulation(SimConfig(seed=42, num_days=90))
        results = sim.run()
        for stat in results:
            assert stat.all_balanced, f"Day {stat.day}: entries not balanced"
            assert stat.system_balanced, f"Day {stat.day}: system not balanced"
