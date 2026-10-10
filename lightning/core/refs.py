"""Document references: ``TYPE-yyyy-mm-dd-NNN``, e.g. ``OUT-2026-09-25-003``.

- Assigned once when the transaction is created and never changed afterwards,
  even if the transaction date is later edited (it is an identifier, not data).
- The counter restarts every day per type. Ledger lines are ``<ref>/<line_no>``.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum

from .errors import ValidationError


class DocType(StrEnum):
    OPN = "OPN"  # Opening balance
    IN = "IN"  # Money in (inflow)
    OUT = "OUT"  # Money out (outflow)
    TRF = "TRF"  # Transfer between own accounts
    CNV = "CNV"  # Conversion (EGP -> USD, cash -> gold)          [M4]
    BUY = "BUY"  # Investment buy                                  [M3]
    SEL = "SEL"  # Investment sell                                 [M3]
    DIV = "DIV"  # Dividend                                        [M3]
    VAL = "VAL"  # Investment revaluation checkpoint; SYSTEM source
    ADJ = "ADJ"  # Reconciliation adjustment                       [M2]


DOC_LABELS = {
    DocType.OPN: "Opening balance",
    DocType.IN: "Money in",
    DocType.OUT: "Money out",
    DocType.TRF: "Internal transfer",
    DocType.CNV: "Conversion",
    DocType.BUY: "Buy",
    DocType.SEL: "Sell",
    DocType.DIV: "Dividend",
    DocType.VAL: "Investment revaluation",
    DocType.ADJ: "Adjustment",
}

REF_RE = re.compile(r"^(?P<type>[A-Z]{2,3})-(?P<date>\d{4}-\d{2}-\d{2})-(?P<seq>\d{3,})$")


def format_ref(doc_type: DocType, on: date, seq: int) -> str:
    if seq < 1:
        raise ValidationError("Sequence must start at 1.")
    return f"{doc_type.value}-{on.isoformat()}-{seq:03d}"


def ref_prefix(doc_type: DocType, on: date) -> str:
    return f"{doc_type.value}-{on.isoformat()}-"


def parse_ref(ref: str) -> tuple[DocType, date, int]:
    match = REF_RE.match(ref or "")
    if not match:
        raise ValidationError(f"'{ref}' is not a valid reference.")
    return DocType(match["type"]), date.fromisoformat(match["date"]), int(match["seq"])


def line_ref(ref: str, line_no: int) -> str:
    return f"{ref}/{line_no}"
