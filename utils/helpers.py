# utils/helpers.py

from typing import Union


def format_number(n: Union[int, float]) -> str:
    """Formats a number using Indian digit grouping, e.g. 1234567 -> '12,34,567'."""

    is_negative = n < 0
    n = abs(n)

    if isinstance(n, float) and not float(n).is_integer():
        whole, _, decimal = f"{n:.2f}".partition(".")
    else:
        whole, decimal = str(int(n)), None

    if len(whole) <= 3:
        formatted = whole
    else:
        last_three = whole[-3:]
        remaining = whole[:-3]

        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]

        if remaining:
            groups.insert(0, remaining)

        formatted = ",".join(groups) + "," + last_three

    if decimal is not None:
        formatted = f"{formatted}.{decimal}"

    return f"-{formatted}" if is_negative else formatted


def format_percentage(n: Union[int, float]) -> str:
    """Formats a number as a percentage string with 2 decimal places, e.g. 45.234 -> '45.23%'."""

    return f"{n:.2f}%"


def safe_divide(a: Union[int, float], b: Union[int, float], default: Union[int, float] = 0):
    """Divides a by b, returning `default` instead of raising on division by zero."""

    if b == 0:
        return default

    return a / b


def truncate_text(text: str, max_len: int = 200) -> str:
    """Truncates text to max_len characters, appending '...' if it was cut off."""

    if len(text) <= max_len:
        return text

    return text[: max_len - 3].rstrip() + "..."


def bytes_to_mb(b: Union[int, float]) -> float:
    """Converts a byte count to megabytes."""

    return b / (1024 * 1024)
