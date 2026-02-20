# VibeSim Development Rules

## Do not 

Do not read the entire code base when starting a session. Refer to what I have asked you to do and only read the neccesary files. 

## Testing Rules

- **Max 50 agents** when running simulations for testing or debugging. Never use 200, 300, or 1000 agents unless the user specifically requests it.
- **Max 90 days** for test simulations unless the user specifically asks for longer runs.
- **After making changes, run `pytest -m smoke` only.** That is 3 tests and takes under 1 second. Do not run the full suite, do not run `test_economics.py`, `test_invariants.py`, or `test_properties.py` unless the user explicitly asks.
- **Never run `test_economics.py` in a loop** trying to tune default parameters. Those tests check that the model responds directionally to shocks. If they fail, fix the model code, not the test thresholds.
- **Avoid running property-based tests** (hypothesis) during iterative development. They are slow. Run them once before committing only if asked.

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

## Documentation Updates

After any major change (new feature, structural refactor, new config params, new simulation phase), update these files:
- **README.md** — feature list, simulation loop description, config table, current development section
- **plan.md** — mark completed phases, add new phases if scope expanded
- **DECISIONS.md** — document the design decision, alternatives considered, and tradeoffs
- **ROADMAP** — update phase status markers ([DONE], etc.)
- **configs/baseline.yaml** — add any new config params with comments
