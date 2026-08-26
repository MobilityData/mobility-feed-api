# Continuous coverage panel (mock)

A local, dependency-free mock of the continuous coverage panel of the feed seal page. It renders
one response of `GET /v1/gtfs_feeds/{id}/continuous_coverage` three ways: a summary card, an
interactive calendar timeline, and the dataset chain.

Built to answer one question — whether the panel can be driven by a single request. It can; the
only thing on the page that does not come from that response is the probation marker pair, which
comes from the `fresh_continuous` criterion the seal page already loads.

## Running it

```bash
scripts/mock-continuous-coverage-start.sh
```

Then open <http://localhost:8095>. Override the port with `PORT=9000 scripts/mock-continuous-coverage-start.sh`.

The page opens on a captured response, so nothing else needs to be running.

## Loading a live feed

Start the API, then put its base URL and a feed ID into the form at the top of the page and press
**Load live**. CORS is open on the API (`allow_origins=["*"]`), so no proxy is needed.

Two gotchas seen locally, neither specific to this mock:

- `scripts/api-start.sh` runs the *global* `uvicorn` and passes the env with `--env-file`. On a
  machine where that leaves `FEEDS_DATABASE_URL` unset when the `Database` singleton is first
  constructed, every DB-backed endpoint returns 500 with
  `AttributeError: 'Database' object has no attribute 'Session'`. Running it out of `api/venv` with
  the env exported works:

  ```bash
  cd api && set -a && . ../config/.env.local && set +a && PYTHONPATH=src venv/bin/python -m uvicorn main:app --port 8097
  ```

- Check nothing stale is already bound to the port (`lsof -nP -iTCP:8080 -sTCP:LISTEN`). An old
  server on 8080 answers requests with code that predates the endpoint.

## What is real and what is not

| Part | Source |
| --- | --- |
| Summary card, timeline bars, overlaps, gaps, chain rows | A real captured response over 20 datasets in `fixtures.js`, or a live API |
| Probation bands and their edges | **Derived from the coverage data** by `probationRuns()` in `app.js`, applying the rule below |
| `CRITERION` in `fixtures.js` | The shape of the `fresh_continuous` entry of `GET /v1/gtfs_feeds/{id}/reliability`, used only to cross-check the derived answer |

`fresh_continuous` has no grace period (`GRACE_PERIODS[FRESH_CONTINUOUS] is None`), so there is
deliberately no grace band on the chart — only probation.

## The probation rule

    a gap is introduced -> IF AND ONLY IF the next upload has no gap -> probation starts on that
    upload's download date -> it runs 180 days -> another gap inside that window restarts the clock.

`probationRuns()` applies exactly this to the items, walking them oldest-first. That is deliberate
rather than reading `probation_ends_at` off the criterion: the reliability endpoint has no field for
the *start*, and deriving it from the chain means every band edge lands on the download date of a
dataset the reader can see in the list below the chart.

The mock then checks its derived end date against the `probation_ends_at` the criterion serves, and
says under the chart whether the two agree.

## The story the fixture tells

The producer publishes about every 30 days, each dataset covering 120 days of service starting 20
days after we fetch it — so consecutive datasets share 91 days and all 20 windows are distinct. A
coverage gap happens when the producer goes quiet: no new dataset arrives until the old one's
service has run out, so the next one starts later than the previous ended.

| Download | What happens |
| --- | --- |
| 2024-01-30 → 2024-10-26 | Ten healthy datasets, 91 days shared each time. |
| **2025-03-14** | 18 days uncovered. `fresh_continuous` fails and, with no grace period, the seal goes that day. |
| **2025-08-07** | 25 more days uncovered. The upload after the first gap was *not* clean, so **no probation starts here** — this is the "if and only if" clause. |
| **2025-09-06** | Clean → probation A starts, running to 2026-03-05. |
| 2025-10-06 | Clean, serving probation A. |
| **2026-02-25** | 21 days uncovered, *inside* probation A → the clock is broken. |
| **2026-03-27** | Clean → probation B starts, running to 2026-09-23. |
| 2026-04-26 → 2026-07-25 | Clean, serving probation B, still open on the fixed today of 2026-08-24. |

So the chart shows two amber bands: probation A faint and cut short where it broke, probation B solid
and still running.

A gap is never repaired retroactively, which is why the gap rows stay in the chain after the feed
recovers. Pulling a later window back over the hole would leave a fresh hole on its far side — and
`overlap_days`, which compares only the older window's end to the newer one's start, would report a
large overlap for it rather than the new hole. Worth knowing about the metric.

## How the chart encodes it

**Two different clocks, one per axis.** This is the thing to understand about the chart:

| Axis | What it measures | What lives there |
| --- | --- | --- |
| Horizontal | **Service dates** — what a dataset claims to cover | the coverage bars, the overlaps between them, the gaps |
| Vertical | **Real time** — when we downloaded each dataset, increasing upward | the seal, probation, today |

Overlaps and gaps are properties of *service* time, so they are horizontal. The seal being withdrawn
and probation running are things that happen in *real* time, so they are horizontal bands and lines
across the vertical axis. Mixing the two — drawing probation as a vertical band over the service
axis — is the easy mistake, and it makes the chart say something untrue.

Because the vertical axis is a real time scale rather than one row per dataset, two consequences fall
out for free:

- The vertical distance between two bars is the real time between those two publications. A quiet
  spell is a visible vertical gap — in this fixture the three gaps show as ~76px jumps against 16px
  for the normal 30-day cadence.
- A probation band can extend past the newest dataset, up to the date it actually ends, which a
  row-per-dataset axis could not express.

The marks themselves:

- **Bars** are each dataset's coverage window. The newest is solid; the rest are lighter.
- **A green rule joining two bars** is the service those two datasets share. Every overlap gets one.
  It is a rule rather than a filled block because a healthy feed has one on every pair, and filling
  them all would bury the bars.
- **A red block** is service that no dataset covers, with a floor of 3px so a 21-day gap stays
  visible against years of service.
- **Amber bands** are probation; the fainter one was later broken by a gap, and stops where it broke.
- **Horizontal lines** mark every gap (`gap of Nd: seal withdrawn`), each probation start and end,
  and today. Probation edges sit on the left rail and gaps and today on the right, so labels a few
  weeks apart do not collide.

## Interactions

- Hover any bar, overlap rule or gap block for its numbers.
- Scroll or drag on the chart to zoom the time axis; the slider under it does the same. A 21-day gap
  is a ~20-pixel sliver across nearly three years of service, so the joins need their own scale to
  be read properly.
- Open **Which fields this card reads** on the summary card to see exactly which `items[0]` fields
  drive each headline number, and which one is counted across the whole chain instead.
- Open **this item's fields** on any chain row for that item's raw JSON.

## Files

- `index.html` — markup
- `styles.css` — light-only tokens and layout
- `app.js` — rendering, the chart option, live fetch
- `fixtures.js` — the captured response and the criterion fixture
- `vendor/echarts.min.js` — Apache ECharts 5.5.1, vendored so the page works offline

## Porting to React

The chart is [Apache ECharts](https://echarts.apache.org/). `chartOption()` in `app.js` builds a
plain option object and nothing else touches the chart, so the React version is
`echarts-for-react` with that same function:

```jsx
import ReactECharts from "echarts-for-react";

<ReactECharts option={chartOption(items, criterion, todayTs)} style={{ height }} notMerge />
```

The pieces doing the work there are `custom` series with a `renderItem` (the coverage bars and the
join marks), two `time` axes, `markArea` on the **y** axis (the probation periods), `markLine` on the
**y** axis (gaps, probation edges, today) and `dataZoom` on the x axis (zoom and pan over service
dates).
