from decimal import Decimal, InvalidOperation

UNICODE_FRACTIONS = {
    "¼": Decimal("0.25"),
    "½": Decimal("0.5"),
    "¾": Decimal("0.75"),
    "⅓": Decimal(1) / Decimal(3),
    "⅔": Decimal(2) / Decimal(3),
    "⅛": Decimal("0.125"),
    "⅜": Decimal("0.375"),
    "⅝": Decimal("0.625"),
    "⅞": Decimal("0.875"),
}


def parse_quantity(value: str | None) -> Decimal | None:
    if value is None:
        return None

    normalized = value.strip().replace(",", ".")

    if not normalized:
        return None

    unicode_result = _parse_unicode_fraction(normalized)

    if unicode_result is not None:
        return unicode_result

    mixed_result = _parse_mixed_fraction(normalized)

    if mixed_result is not None:
        return mixed_result

    fraction_result = _parse_fraction(normalized)

    if fraction_result is not None:
        return fraction_result

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _parse_unicode_fraction(value: str) -> Decimal | None:
    if value in UNICODE_FRACTIONS:
        return UNICODE_FRACTIONS[value]

    for symbol, fraction_value in UNICODE_FRACTIONS.items():
        if value.endswith(symbol):
            whole_part = value.removesuffix(symbol)

            if whole_part.isdigit():
                return Decimal(whole_part) + fraction_value

    return None


def _parse_mixed_fraction(value: str) -> Decimal | None:
    parts = value.split()

    if len(parts) != 2:
        return None

    whole_part, fraction_part = parts

    if not whole_part.isdigit():
        return None

    fraction = _parse_fraction(fraction_part)

    if fraction is None:
        return None

    return Decimal(whole_part) + fraction


def _parse_fraction(value: str) -> Decimal | None:
    numerator_text, separator, denominator_text = value.partition("/")

    if not separator:
        return None

    if not numerator_text.isdigit() or not denominator_text.isdigit():
        return None

    denominator = Decimal(denominator_text)

    if denominator == 0:
        return None

    return Decimal(numerator_text) / denominator
