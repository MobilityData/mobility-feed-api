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

A simulated verdict in `seal_criterion` would be indistinguishable from an earned one — the
row carries no provenance — so writing one is refused by default, and a traced dry run
marches with writing suppressed. `check_simulated_write_allowed` holds the exception and its
conditions: an explicit payload flag, an environment on the allowlist, and not the production
tunnel port. Everything that decides whether a fabricated status may reach the tables lives in
this module, so the rule can be read in one place.

Day offsets are counted from each feed's own march start, so day 0 is that feed's first
evaluated day: the one denied a grace period. Anchoring to the run's `start_date` instead
would point at days a younger feed never marched.
"""

import logging
import os
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from shared.common.seal_criteria import CriterionStatus
from tasks.seal_of_reliability.evaluators.base import CriterionObservation
from tasks.seal_of_reliability.state_machine import SealCriterionState, phase

logger = logging.getLogger(__name__)

# Every field of the state a day leaves behind, minus the two that identify it — those are
# already on the row as `stable_id` and `criterion`. Taken from the dataclass rather than
# listed, so a field added to SealCriterionState shows up in the trace without touching
# this file, which is the same trick `seal_updater._snapshot_row` uses for the snapshots.
TRACED_STATE_FIELDS: Tuple[str, ...] = tuple(
    f.name
    for f in dataclass_fields(SealCriterionState)
    if f.name not in ("feed_id", "criterion")
)

# Fields that advance on their own inside a stretch where nothing actually happened, and so
# must not break a run when collapsing. `day` and `evaluated_at` move every day;
# `last_verdict_at` moves on every verdict; and during a confirmed failure streak
# `last_observed_failure_at`, `last_confirmed_failure_at` and `probation_start` are all
# re-stamped daily — probation_start to tomorrow, which is why the longest runs would never
# collapse if it counted. `reason` is prose and differs per simulated day.
#
# Everything else is part of the signature, so a field added to SealCriterionState breaks
# runs by default rather than being silently ignored: too eager beats invisible.
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

# Cap on the trace a single call returns. A year x a batch of feeds x six criteria would be
# a response no one can read and Cloud Logging would drop; a simulation is a small thing.
MAX_TRACE_ROWS: int = 2000

# Payload keys inside a criterion that do something other than name days. Status names are a
# closed set, so there is no collision.
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

    A scenario is usually "this criterion holds one status, except on these days". `default`
    is that baseline, and the named days are the exceptions on top of it. Without a baseline
    the unnamed days fall through to the real evaluator, which is only useful where the
    source data says something: locally `fresh_coverage` has no dataset history to read and
    every unnamed day comes back UNKNOWN, so a scenario built purely from exceptions never
    leaves `never_evaluated`.

    Overriding the periods matters for a criterion that has none — `official` and `stable`
    are point-in-time checks, so a forced failure confirms the same day and the trace shows
    nothing about debouncing. `fresh_coverage` ships with 14 days of grace and 180 of
    probation, so it needs no lending to exercise either.

    Only ever applied to a dry run, so no fabricated status or policy can reach the seal
    tables.
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

        Offsets are stringified rather than left as ints: they share the dict with
        `grace_days` and `probation_days`, and Flask's jsonify sorts keys, which raises on a
        dict mixing str and int. JSON object keys are strings anyway, so the response shape
        is unchanged.
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

    Offsets rather than dates because a scenario is about the shape of a history — "it fails
    on day 3" — not about a calendar. Anchoring per feed rather than to the window start is
    what makes day 0 the feed's first evaluation, the one denied a grace period.

    `default` is the status every unnamed day takes. Omit it and unnamed days fall through to
    the real evaluator instead, which is what you want when the source data has something to
    say and useless when it does not.

    `grace_days` and `probation_days` are optional and override the criterion's own values
    for the run. Omit either to keep the evaluator's; pass null to mean it has none.
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
            "have seal state, only_missing (default true) excludes them — pass "
            "only_missing=false to march them again."
        )
    for criterion, forced in simulation.items():
        beyond = sorted(offset for offset in forced.days if offset >= longest_march)
        if beyond:
            raise ValueError(
                f"Simulated day(s) {beyond} for {criterion!r} are past the end of every "
                f"feed's march; the longest here is {longest_march} day(s), so valid "
                f"offsets are 0..{max(longest_march - 1, 0)}"
            )


def observe(evaluator, ctx, simulation, offset: int) -> CriterionObservation:
    """The criterion's own verdict, unless this day is simulated.

    A named day wins over the baseline, and with neither the day falls through to the real
    evaluator — so a simulation ranges from real data with a couple of overrides to a wholly
    synthetic history, depending on whether `default` was given.
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

    Carries the whole state rather than a summary, so a trace answers the same questions the
    stored row would — when the current streak began, when a verdict was last reached — and
    a reader never has to run the march again to see a field that was left out.

    Flask's jsonify sorts keys, so the order here is for reading the source, not the
    response.
    """
    row = {
        "stable_id": feed.stable_id,
        "criterion": evaluator.name.value,
        "day": offset,
        # No `date`: `evaluated_at` is the same day by construction, since the march
        # evaluates every criterion once per day and `transition` stamps it every time.
        "phase": phase(state).value,
        "simulated": observation.reason.startswith("simulated:"),
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

    A year of trace is mostly repetition — a criterion sits in one situation for weeks. Each
    run is reported as its first day, its last day, and how many days sat between them, so
    the boundaries stay exact while the middle collapses.

    Rows are grouped by feed and criterion first: the march emits them day-major, so
    consecutive entries in the flat list are different feeds, not consecutive days.
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


# Environments in which a forced verdict may be written to the seal tables. Deliberately a
# closed list rather than "anything but prod": an ENVIRONMENT that is unset or misspelled
# refuses, so a deployment that forgets to set it cannot fabricate seal history. dev and qa are
# both in, by decision — they are where scenarios get exercised. Note dev and qa share one
# Cloud SQL instance, so a simulated write in either is one database name away from the other's
# data; the response flag and the warning log are the only marks a fabricated row leaves.
SIMULATED_WRITE_ENVIRONMENTS: Tuple[str, ...] = ("local", "dev", "qa", "test")

# The local port production is reached on when a tunnel is up, by team convention. Refusing it
# is a guard rail, not a guarantee: the port is a property of how the tunnel was started rather
# than of the database, so a tunnel opened on another port walks straight past this. It is here
# because ENVIRONMENT describes the process, not the write target — a local run labelled `local`
# can be pointed at production through a tunnel and would otherwise pass every other check. The
# actual control is connecting to production as a read-only user.
PROD_TUNNEL_PORT: int = 9901


def _connection_port(db_session: Session) -> Optional[int]:
    """The port this session is connected on, or None if it cannot be determined."""
    try:
        return db_session.get_bind().url.port
    except Exception:  # defensive: never let the guard rail itself break a run
        logger.warning(
            "Could not determine the database port for the simulated-write check"
        )
        return None


def check_simulated_write_allowed(simulate: dict, db_session: Session) -> None:
    """Refuse to write forced verdicts anywhere they could be mistaken for real history.

    A simulated verdict in `seal_criterion` is indistinguishable from an earned one — the row
    carries no provenance — so where it may be written is decided here, by the deployment
    rather than by the payload. Two conditions, both about the target: the environment has to
    be one where fabricated data is expected, and the connection must not be production's
    tunnel port.
    """
    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    if environment not in SIMULATED_WRITE_ENVIRONMENTS:
        raise ValueError(
            f"a simulated write is refused with ENVIRONMENT={environment or 'unset'!r}: "
            f"forced verdicts may only be written in {list(SIMULATED_WRITE_ENVIRONMENTS)}, "
            f"and an unset environment is treated as production."
        )

    port = _connection_port(db_session)
    if port == PROD_TUNNEL_PORT:
        raise ValueError(
            f"a simulated write is refused on port {PROD_TUNNEL_PORT}: that is the "
            f"production database's tunnel port, whatever ENVIRONMENT={environment!r} claims."
        )

    logger.warning(
        "SIMULATED WRITE in ENVIRONMENT=%s on port %s: forced statuses for %s are being "
        "written to the seal tables. These rows are indistinguishable from earned ones.",
        environment,
        port,
        sorted(simulate),
    )
