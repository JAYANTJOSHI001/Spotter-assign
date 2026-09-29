"""Request-scoped external call budget enforcement and recording."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from apps.providers.errors import BudgetExceeded


@dataclass(frozen=True, slots=True)
class CallRecord:
    """Record of an external API call made during request processing."""

    provider: str
    purpose: str
    ms: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CallContext:
    """Context manager and tracker for an individual external call."""

    def __init__(self, budget: CallBudget, provider: str, purpose: str) -> None:
        self._budget = budget
        self.provider = provider
        self.purpose = purpose
        self.status = "unknown"
        self.ms = 0
        self._start_time: float = 0.0
        self._finished = False

    def __enter__(self) -> CallContext:
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self._finished:
            elapsed_ms = int((time.perf_counter() - self._start_time) * 1000)
            if exc_type is not None:
                status = getattr(exc_val, "code", exc_type.__name__)
            else:
                status = self.status if self.status != "unknown" else "ok"
            self.finish(ms=elapsed_ms, status=status)

    def finish(self, ms: int, status: str) -> None:
        if not self._finished:
            self._finished = True
            self.ms = ms
            self.status = status
            self._budget._records.append(
                CallRecord(
                    provider=self.provider,
                    purpose=self.purpose,
                    ms=self.ms,
                    status=self.status,
                )
            )


class CallBudget:
    """Request-scoped budget tracking and enforcing external call limits."""

    def __init__(self, max_calls: int = 3) -> None:
        self.max_calls = max_calls
        self._records: list[CallRecord] = []
        self._active_calls: int = 0

    @property
    def calls(self) -> list[dict[str, Any]]:
        """Return list of call records as dictionaries."""
        return [record.to_dict() for record in self._records]

    @property
    def records(self) -> list[CallRecord]:
        """Return list of CallRecord dataclass instances."""
        return list(self._records)

    @property
    def calls_count(self) -> int:
        """Total calls recorded or in progress."""
        return len(self._records) + self._active_calls

    def consume(self, provider: str, purpose: str) -> CallContext:
        """Reserve a call slot or raise BudgetExceeded if budget is exhausted."""
        if len(self._records) >= self.max_calls:
            raise BudgetExceeded(
                f"External call budget of {self.max_calls} calls exceeded. "
                f"Attempted {purpose} call to {provider}."
            )
        return CallContext(self, provider, purpose)
