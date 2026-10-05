"""Service-layer operations for helpers workflows.

Business rules live here so views and commands can share the same behavior.
"""

from decimal import Decimal, InvalidOperation


def as_decimal(value):
    """Provide the as decimal operation used by the application service layer."""
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def parse_bool_cell(value):
    """Parse bool cell data into the application representation."""
    if value is True:
        return True
    if value in (False, None, ""):
        return False
    return str(value).strip().lower() in {"true", "true()", "yes", "y", "1", "x"}
