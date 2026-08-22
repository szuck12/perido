# __init__.py
# Perido — a local-first command-line Pomodoro timer with a focus journey.

__version__ = "0.2.0"


class PeridoError(Exception):
    """A recoverable, user-facing error from a Perido operation.

    The CLI catches this, prints the message to stderr, and exits
    with status 1. Messages may be multi-line when a hint helps.
    """
