#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Forced per-day statuses and the day-by-day trace, for inspecting a backfill march.

Neither may write: a simulated verdict is indistinguishable from an earned one, the row
carrying no provenance. The trace is the substitute, and carries every field a snapshot
would have stored.

Day offsets count from each feed's own march start, so day 0 is its first evaluated day —
the one denied a grace period.
"""

import logging
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from shared.common.seal_criteria import CriterionStatus
from tasks.seal_of_reliability.evaluators.base import CriterionObservation
from tasks.seal_of_reliability.state_machine import SealCriterionState, phase

logger = logging.getLogger(__name__)

# Derived from the dataclass, not listed, so a new state field reaches the trace on its own —
# the same trick `seal_updater._snapshot_row` uses. `feed_id` and `criterion` are already on
# the row as `stable_id` and `criterion`.
TRACED_STATE_FIELDS: Tuple[str, ...] = tuple(
    f.name
    for f in dataclass_fields(SealCriterionState)
    if f.name not in ("feed_id", "criterion")
)

# Fields that advance on their own inside a stretch where nothing happened, so collapsing
# must ignore them. `probation_start` is the load-bearing one: a confirmed streak re-stamps it
# to tomorrow every day, so counting it would stop the longest runs ever collapsing.
# Everything else is part of the signature, so a new state field breaks runs rather than being
# silently ignored.
TICKING_FIELDS: frozenset = frozenset(
    {
        "day",
        "evaluated_at",
        "last_verdict_at",
        "last_observed_failure_at",
        "last_confirmed_failure_at",
        "probation_start",
        "reason",
    }
)

# Cap on the trace one call returns: a year x a batch x six criteria is a response Cloud
# Logging would drop. The march is feed-major, so hitting the cap drops the last feeds of the
# batch entirely rather than the last days of every feed — whichever feeds it does report,
# it reports whole.
MAX_TRACE_ROWS: int = 2000

# Payload keys that do something other than name days. Status names are a closed set, so
# there is no collision.
GRACE_KEY = "grace_days"
PROBATION_KEY = "probation_days"
DEFAULT_KEY = "default"
_RESERVED_KEYS = (DEFAULT_KEY, GRACE_KEY, PROBATION_KEY)

# Distinguishes "not given" — use the evaluator's own value — from an explicit null, which
# means the criterion has no such period.
_UNSET = object()


@dataclass(frozen=True)
class CriterionSimulation:
    """What a payload sets for one criterion: a baseline, named days, and optionally policy.

    `default` is the baseline and the named days are exceptions on it. Without a baseline the
    unnamed days fall through to the evaluator, which says nothing useful where the source
    data is absent — `fresh_coverage` answers UNKNOWN for every day on a local database.

    Lending periods matters only for a criterion that has none: `official` and `stable` are
    point-in-time checks, so a forced failure confirms the same day.
    """

    days: Mapping[int, CriterionStatus] = field(default_factory=dict)
    baseline: Optional[CriterionStatus] = None
    grace_period: Optional[timedelta] = None
    probation_period: Optional[timedelta] = None
    grace_overridden: bool = False
    probation_overridden: bool = False

    def status_on(self, offset: int) -> Optional[CriterionStatus]:
        """The status this payload forces on `offset`, or None to ask the evaluator."""
        forced = self.days.get(offset)
        return forced if forced is not None else self.baseline

    def grace_for(self, evaluator) -> Optional[timedelta]:
        return self.grace_period if self.grace_overridden else evaluator.grace_period

    def probation_for(self, evaluator) -> Optional[timedelta]:
        return (
            self.probation_period
            if self.probation_overridden
            else evaluator.probation_period
        )

    def as_reported(self) -> dict:
        """The echo returned in the report, so a run states what it was told to pretend.

        Offsets are stringified because they share the dict with `grace_days`, and jsonify
        sorts keys — which raises on a dict mixing str and int.
        """
        echo: Dict[str, Any] = {
            str(offset): status.value for offset, status in sorted(self.days.items())
        }
        if self.baseline is not None:
            echo[DEFAULT_KEY] = self.baseline.value
        if self.grace_overridden:
            echo[GRACE_KEY] = (
                self.grace_period.days if self.grace_period is not None else None
            )
        if self.probation_overridden:
            echo[PROBATION_KEY] = (
                self.probation_period.days
                if self.probation_period is not None
                else None
            )
        return echo


def policy_for(evaluator, simulation) -> tuple:
    """The (grace, probation) this run applies to `evaluator` — its own unless overridden."""
    forced = (simulation or {}).get(evaluator.name.value)
    if forced is None:
        return evaluator.grace_period, evaluator.probation_period
    return forced.grace_for(evaluator), forced.probation_for(evaluator)


def _parse_period(value, criterion: str, key: str) -> Optional[timedelta]:
    """A whole number of days, or null meaning the criterion has no such period."""
    if value is None:
        return None
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{key} for {criterion!r} must be a whole number of days or null, got {value!r}"
        )
    if days < 0:
        raise ValueError(
            f"{key} for {criterion!r} cannot be negative; got {days}. Use null to mean the "
            f"criterion has no such period."
        )
    return timedelta(days=days)


def parse_simulation(
    simulate: Optional[dict], evaluators: Sequence
) -> Dict[str, CriterionSimulation]:
    """Turn the `simulate` payload into criterion -> CriterionSimulation.

    Shape, offsets counted from each feed's own march start::

        {"fresh_coverage": {"default": "pass", "fail": [3, 4], "unknown": [8]}}

    Offsets rather than dates: a scenario is the shape of a history, not a calendar. Per feed
    rather than per window, so day 0 is the feed's first evaluation — the one denied grace.

    `default` is what unnamed days take; omit it and they fall through to the evaluator.
    `grace_days` and `probation_days` override the criterion's own — omit to keep them, null
    to mean it has none.
    """
    if not simulate:
        return {}

    known = {evaluator.name.value for evaluator in evaluators}
    forced_statuses = {
        status.value for status in CriterionStatus if status.is_verdict
    } | {
        CriterionStatus.UNKNOWN.value,
        CriterionStatus.NOT_APPLICABLE.value,
    }

    parsed: Dict[str, CriterionSimulation] = {}
    for criterion, by_status in simulate.items():
        if criterion not in known:
            raise ValueError(
                f"Cannot simulate unknown criterion {criterion!r}. This run evaluates: "
                f"{sorted(known)}"
            )
        by_status = dict(by_status or {})
        grace = by_status.pop(GRACE_KEY, _UNSET)
        probation = by_status.pop(PROBATION_KEY, _UNSET)
        baseline = by_status.pop(DEFAULT_KEY, None)
        if baseline is not None and baseline not in forced_statuses:
            raise ValueError(
                f"Cannot simulate {DEFAULT_KEY} status {baseline!r} for {criterion!r}. "
                f"Valid: {sorted(forced_statuses)}"
            )

        days: Dict[int, CriterionStatus] = {}
        for status, offsets in by_status.items():
            if status not in forced_statuses:
                raise ValueError(
                    f"Cannot simulate status {status!r} for {criterion!r}. Valid: "
                    f"{sorted(forced_statuses)} — plus {list(_RESERVED_KEYS)}"
                )
            for offset in offsets or []:
                offset = int(offset)
                if offset < 0:
                    raise ValueError(
                        f"Simulated day offsets are counted from the march start and cannot "
                        f"be negative; got {offset} for {criterion!r}"
                    )
                if offset in days and days[offset].value != status:
                    raise ValueError(
                        f"Day {offset} of {criterion!r} is simulated twice, as "
                        f"{days[offset].value!r} and {status!r}"
                    )
                days[offset] = CriterionStatus(status)

        parsed[criterion] = CriterionSimulation(
            days=days,
            baseline=(CriterionStatus(baseline) if baseline is not None else None),
            grace_period=(
                None if grace is _UNSET else _parse_period(grace, criterion, GRACE_KEY)
            ),
            probation_period=(
                None
                if probation is _UNSET
                else _parse_period(probation, criterion, PROBATION_KEY)
            ),
            grace_overridden=grace is not _UNSET,
            probation_overridden=probation is not _UNSET,
        )
    return parsed


def check_simulation_fits(
    simulation: Dict[str, Dict[int, CriterionStatus]],
    longest_march: int,
) -> None:
    """Reject offsets no march reaches, rather than letting them silently do nothing.

    A typo like day 400 in an eight-day window would otherwise look like it worked.
    """
    if not longest_march:
        # Nothing was selected, so blaming the offsets would send the reader to the wrong
        # parameter entirely. `only_missing` excluding an already-backfilled feed is the
        # usual cause.
        raise ValueError(
            "Nothing to simulate: no feed was selected for this run. If the feeds already "
            "hold every criterion of the run, only_missing (default true) excludes them — "
            "pass only_missing=false to march them again."
        )
    for criterion, forced in simulation.items():
        beyond = sorted(offset for offset in forced.days if offset >= longest_march)
        if beyond:
            raise ValueError(
                f"Simulated day(s) {beyond} for {criterion!r} are past the end of every "
                f"feed's march; the longest here is {longest_march} day(s), so valid "
                f"offsets are 0..{max(longest_march - 1, 0)}"
            )


def is_simulated(simulation, evaluator, offset: int) -> bool:
    """Whether this criterion's status on this day is forced, and so is nobody else's to set.

    A simulated run asks what the state machine does with a given sequence of statuses. A day
    that is only sometimes forced — because something real was recorded for it — would answer
    a question nobody asked.
    """
    entry = simulation.get(evaluator.name.value)
    return entry is not None and entry.status_on(offset) is not None


def observe(evaluator, ctx, simulation, offset: int) -> CriterionObservation:
    """The criterion's own verdict, unless this day is simulated.

    A named day wins over the baseline; with neither, the day falls through to the evaluator.
    """
    entry = simulation.get(evaluator.name.value)
    forced = entry.status_on(offset) if entry else None
    if forced is None:
        return evaluator.evaluate(ctx)
    named = entry.days.get(offset) is not None
    return CriterionObservation(
        criterion=evaluator.name,
        observed_status=forced,
        reason=(
            f"simulated: {forced.value} on day {offset}"
            if named
            else f"simulated: {forced.value} by default"
        ),
    )


def _as_day(value):
    """Render a state value for the trace: statuses as their name, timestamps as their day.

    The march evaluates at midnight UTC, so a date loses nothing and reads better than a
    full timestamp repeated down a year of rows.
    """
    if isinstance(value, CriterionStatus):
        return value.value
    if hasattr(value, "date"):
        return value.date().isoformat()
    return value


def trace_row(feed, evaluator, offset: int, observation, state) -> dict:
    """One day of one criterion: every seal_criterion field, plus where it came from.

    The whole state rather than a summary, so a trace answers what the stored row would.
    jsonify sorts keys, so the order here is for reading the source, not the response.
    """
    row = {
        "stable_id": feed.stable_id,
        "criterion": evaluator.name.value,
        "day": offset,
        # No `date`: `evaluated_at` is the same day by construction, since the march
        # evaluates every criterion once per day and `transition` stamps it every time.
        "phase": phase(state).value,
        "simulated": observation.reason.startswith("simulated:"),
        # A day the nightly job had already recorded, so the march used its verdict rather
        # than reconstructing one. Part of the collapse signature, so the switch from
        # reconstructed days to recorded ones shows up as a run boundary.
        "recorded": observation.reason.startswith("recorded:"),
        "reason": observation.reason,
    }
    for name in TRACED_STATE_FIELDS:
        row[name] = _as_day(getattr(state, name))
    return row


def _signature(row: dict) -> tuple:
    """What makes a day different from the one before it, ignoring the ticking fields."""
    return tuple(
        sorted((key, value) for key, value in row.items() if key not in TICKING_FIELDS)
    )


def collapse_runs(rows: Sequence[dict]) -> List[dict]:
    """Collapse consecutive days in which nothing changed into one entry per run.

    Each run reports its first day, its last, and the count between, so the boundaries stay
    exact while the middle goes. Grouped by feed and criterion first: the march emits rows
    feed-major but criterion-interleaved, so neighbours in the flat list are different
    criteria of the same day, not consecutive days.
    """
    grouped: Dict[Tuple[str, str], List[dict]] = {}
    for row in rows:
        grouped.setdefault((row["stable_id"], row["criterion"]), []).append(row)

    collapsed: List[dict] = []
    for series in grouped.values():
        series.sort(key=lambda row: row["day"])
        run: List[dict] = []
        for row in series:
            if run and _signature(run[-1]) == _signature(row):
                run.append(row)
                continue
            if run:
                collapsed.append(_as_run(run))
            run = [row]
        if run:
            collapsed.append(_as_run(run))
    return collapsed


def _as_run(run: Sequence[dict]) -> dict:
    """One unchanged stretch: its first day, its last, and the count between them."""
    entry = {"days": len(run), "first": run[0]}
    if len(run) > 1:
        entry["last"] = run[-1]
        entry["in_between"] = len(run) - 2
    return entry


def refuse_simulated_write() -> None:
    """A forced verdict must never reach the seal tables, in any environment.

    The row carries no provenance, so a fabricated verdict and an earned one are the same
    row. The trace is the substitute, and `test_every_traced_day_matches_its_stored_snapshot`
    pins that it holds every field a snapshot would.
    """
    raise ValueError(
        "simulate requires dry_run: forced verdicts must never be written to the seal "
        "tables, where nothing would mark them as simulated. Use trace to read the state "
        "each day would have stored."
    )
