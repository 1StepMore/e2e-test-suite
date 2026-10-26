"""Shared verdict-status sets for the validation report and diff."""

from __future__ import annotations

PASS_LIKE_STATUSES = frozenset({"passed", "recovered", "partial-pass"})
