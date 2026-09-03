# survivor-board

Circa Survivor 2026 model. The board publishes to
https://cnicholsonoffice.github.io/survivor-board/

Everything runs on GitHub Actions. There is no terminal and nothing to install.

## It updates itself

The model re-runs **every day at 5am PT**, plus again **Saturday at noon PT**
(before the 4pm PT deadline). Each run pulls the latest schedule and betting
lines from nflverse, refits the ratings, re-solves the remaining season, and
commits a new `index.html`. Pages picks it up within a minute.

If nothing changed, it commits nothing.

## Locking a pick (the only thing you do by hand)

Once you submit a team to Circa:

1. Go to the **Actions** tab
2. Click **Survivor board** in the left sidebar
3. Click **Run workflow**
4. Type the team abbreviation into the **lock** box, e.g. `LAC`
5. Click the green **Run workflow** button

That marks the team used, freezes what the model believed at that moment into
the season archive, and republishes. Leave the box blank for a plain refresh.

The `leg` box is an override (`W3`, `TG`, `XM`) — normally leave it blank, the
model works out which leg is live from the schedule.

## What's here

| path | what it is |
|---|---|
| `src/` | the model — data, ratings, win probability, optimizer, renderer |
| `state.json` | teams used, keyed by leg, plus the archive of locked picks |
| `index.html` | the published board (overwritten each run) |
| `out/payload.json` | every number behind the board, as JSON |
| `.github/workflows/survivor.yml` | the schedule and the run steps |

`state.json` is the only file that must be correct by hand. If it is wrong, the
whole plan is wrong.

## Two things worth knowing

- Python deps are **pinned** (`pandas==3.0.2`, `numpy==2.4.4`, `scipy==1.17.1`)
  so a future release can't quietly change the board while nobody is watching.
- If a scheduled run ever fails, GitHub emails you. If the schedule goes quiet
  after a long idle stretch, one click on **Run workflow** wakes it back up.
