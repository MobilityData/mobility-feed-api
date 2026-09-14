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
"""What the Feed Detail page shows of the seal, reduced to a comparable value.

The website caches a feed's page until something tells it the feed changed, so the nightly job
has to say when its own output changed. Not every run does: `evaluated_at` moves on every
criterion of every evaluated feed every night, and the page does not render it. Busting the
cache on that would be the same as not caching at all.

So the comparison is made against a *signature* - only the values the page actually renders,
and none of the timestamps. The rendered fields are:

* `has_seal` - the badge in the header.
* per criterion, `status` - `confirmed_status`, the debounced verdict.
* per criterion, `in_grace_period` and `on_probation` - the two badges beside it.

"""

from typing import Dict, Iterable, Optional, Tuple

from tasks.seal_of_reliability.state_machine import SealCriterionState, phase

CriterionSignature = Tuple[str, str, str]

FeedSignature = Tuple[Optional[bool], Tuple[CriterionSignature, ...]]


def criterion_signature(state: SealCriterionState) -> CriterionSignature:
    """The rendered state of one criterion, with no timestamps in it."""
    return (
        state.criterion.value,
        state.confirmed_status.value,
        phase(state).value,
    )


def feed_signature(
    has_seal: Optional[bool], states: Iterable[SealCriterionState]
) -> FeedSignature:
    """The rendered seal state of one feed.

    `has_seal` is None on a partial-criteria run, where the roll-up is skipped: passing None on
    both sides leaves the decision to the criteria that were actually evaluated.
    """
    return (
        has_seal,
        tuple(sorted(criterion_signature(state) for state in states)),
    )


def page_state_changed(
    previous_states: Dict[str, SealCriterionState],
    new_states: Dict[str, SealCriterionState],
    had_seal: Optional[bool],
    has_seal: Optional[bool],
) -> bool:
    """Whether the Feed Detail page would render the seal differently after this run.

    Both dicts are keyed by criterion name, as `seal_updater` keys them. `new_states` is the
    merged view - this run's states over the stored ones - so a criterion the run did not
    re-evaluate carries the same value on both sides and cannot register as a change.

    An empty `previous_states` means the feed has no `seal_criterion` row at all, so this is its
    first evaluation: there is no earlier state to compare against and the seal is new, which
    the page has never shown. That is a change.
    """
    if not previous_states:
        return True
    return feed_signature(had_seal, previous_states.values()) != feed_signature(
        has_seal, new_states.values()
    )
