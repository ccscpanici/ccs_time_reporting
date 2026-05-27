from decimal import Decimal, InvalidOperation


def as_decimal(value):
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def parse_bool_cell(value):
    if value is True:
        return True
    if value in (False, None, ""):
        return False
    return str(value).strip().lower() in {"true", "true()", "yes", "y", "1", "x"}
