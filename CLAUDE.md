# VibeSim Development Rules

## Testing Rules

- **Max 50 agents** when running simulations for testing or debugging. Never use 200, 300, or 1000 agents unless the user specifically requests it.
- **Max 90 days** for test simulations unless the user specifically asks for longer runs.
- **Run targeted tests**, not the full suite. If you changed `markets.py`, run `test_accounting.py` and `test_smoke.py` — not every test file.
- **Never run `test_economics.py` in a loop** trying to tune default parameters. Those tests check that the model responds directionally to shocks. If they fail, fix the model code, not the test thresholds.
- **Avoid running property-based tests** (hypothesis) during iterative development. They are slow. Run them once before committing.
- **One quick smoke test** (`pytest -m smoke`) is enough to verify basic correctness after most changes.

## What Matters

The simulation is a **sandbox for hobbyists and academics** to explore the effects of fiscal/monetary policy on simulated agents. The important things are:

1. **The simulation runs** and produces reasonable output
2. **The ledger is internally consistent** (debits = credits)
3. **Policy shocks produce directionally correct responses**
4. **The code is clean and importable** as a Python package

The double-entry bookkeeping is an implementation detail that ensures consistency. It is NOT the product. Do not over-emphasize accounting language in docs or comments.

## Code Changes

- Fix bugs in model logic (like inverted wage adjustment). Do not spend time tuning default config parameters to make the economy "look right" — that is the user's job.
- The scenario presets (stimulus, austerity, etc.) are saved settings, not correctness tests. They should work directionally but don't need to produce specific numeric outcomes.
- Keep test runtimes under 2 minutes total for the core suite (smoke + accounting + io).
