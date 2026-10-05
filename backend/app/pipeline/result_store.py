"""Short-lived, in-memory store of server-produced verification outcomes.

Used only so that alternative wording works from the SERVER's own validated result (never from
client-supplied evidence). Process memory only; bounded; no persistence (MVP).
"""

from __future__ import annotations

from collections import OrderedDict

from app.domain.claim import ConfirmedClaim
from app.domain.results import VerificationOutcome


class ResultStore:
    def __init__(self, max_items: int = 500) -> None:
        self._items: OrderedDict[tuple[str, str], tuple[ConfirmedClaim, VerificationOutcome]] = (
            OrderedDict()
        )
        self._max = max_items

    def put(self, run_id: str, claim: ConfirmedClaim, outcome: VerificationOutcome) -> None:
        key = (run_id, claim.claim_id)
        self._items[key] = (claim, outcome)
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def get(self, run_id: str, claim_id: str) -> tuple[ConfirmedClaim, VerificationOutcome] | None:
        return self._items.get((run_id, claim_id))


RESULTS = ResultStore()
