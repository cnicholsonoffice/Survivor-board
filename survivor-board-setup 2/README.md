# Circa Survivor 2026 — model

Source of truth for the survivor model. `state.json` is the only
hand-maintained file.

Run from this directory:

    pip install pandas numpy scipy
    python3 src/run_week.py

Writes `out/survivor.html`. Copy to `../index.html` to publish via
GitHub Pages.

Lock a submitted pick:

    python3 src/run_week.py --leg W2 --lock SF
    python3 src/run_week.py --leg W2 --entry mini-survivor --lock LAC

`data/` and `out/` are regenerated on every run and are not committed.
