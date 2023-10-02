def vert(condition: bool, error_message: str = '') -> None:
    """If condition is False, raises a ValueError with the given message."""
    if not condition:
        raise ValueError(error_message)

def tert(condition: bool, error_message: str = '') -> None:
    """If condition is False, raises a TypeError with the given message."""
    if not condition:
        raise TypeError(error_message)


class UsageError(BaseException):
    ...


def tressa(condition: bool, error_message: str) -> None:
    """Raises a UsageError with the given error_message if
        the condition is False. Replacement for assert statements and
        AssertionError.
    """
    if not condition:
        raise UsageError(error_message)
