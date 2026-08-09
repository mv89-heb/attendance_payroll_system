from decimal import Decimal, ROUND_HALF_UP

def to_decimal(value, precision=4) -> Decimal:
    if value is None:
        return Decimal("0.0000")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))

def round_money(amount: Decimal, places=2) -> Decimal:
    path = "0." + ("0" * (places - 1)) + "1" if places > 0 else "0"
    return amount.quantize(Decimal(path), rounding=ROUND_HALF_UP)
