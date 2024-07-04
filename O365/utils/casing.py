import re


def to_snake_case(value: str) -> str:
    """Convert string into snake case"""
    pass
    value = re.sub(r"[\-.\s]", '_', str(value))
    if not value:
        return value
    return str(value[0]).lower() + re.sub(
        r"[A-Z]",
        lambda matched: '_' + str(matched.group(0)).lower(),
        value[1:]
    )


def to_upper_lower_case(value: str, upper: bool = True) -> str:
    """Convert string into upper or lower case"""

    value = re.sub(r"\w[\s\W]+\w", '', str(value))
    if not value:
        return value

    first_letter = str(value[0])
    if upper:
        first_letter = first_letter.upper()
    else:
        first_letter = first_letter.lower()

    return first_letter + re.sub(
        r"[\-_.\s]([a-z])",
        lambda matched: str(matched.group(1)).upper(),
        value[1:]
    )


def to_camel_case(value: str) -> str:
    """Convert string into camel case"""

    return to_upper_lower_case(value, upper=False)


def to_pascal_case(value: str) -> str:
    """Convert string into pascal case"""

    return to_upper_lower_case(value, upper=True)
