"""Cursor pagination for lists that grow from the top.

Page numbers answer "skip the first N rows", which two things spoil on a feed:
the database walks and throws away those N rows, and anything added meanwhile
shifts the whole list down, so the next page repeats what was just read. A
cursor names the row the reader stopped at instead, so the database seeks
straight to it through the index and new arrivals change nothing.
"""

import base64
import binascii
from typing import NamedTuple

from django.db.models import Q
from django.utils.dateparse import parse_datetime


class CursorPage(NamedTuple):
    rows: list
    next_cursor: str


def cursor_page(queryset, per_page, cursor=None, field="created"):
    """One page of `queryset`, newest first, plus the cursor for the next one.

    The pair (field, id) is what a cursor points at: the date alone repeats,
    and rows sharing a date would then be skipped or served twice.
    """
    queryset = queryset.order_by(f"-{field}", "-id")

    position = _decode(cursor)
    if position:
        moment, last_id = position
        queryset = queryset.filter(
            Q(**{f"{field}__lt": moment}) | Q(**{field: moment, "id__lt": last_id})
        )

    # One row past the page: its presence is the answer to "is there more",
    # without a second query counting what is left.
    rows = list(queryset[: per_page + 1])
    if len(rows) > per_page:
        rows = rows[:per_page]
        return CursorPage(rows, _encode(rows[-1], field))
    return CursorPage(rows, "")


def _encode(row, field):
    raw = f"{getattr(row, field).isoformat()}|{row.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode(cursor):
    """A cursor nobody can read is a cursor whose shape we are free to change.

    Anything unreadable is treated as no cursor at all: a hand-edited address
    then reads the list from the top instead of answering with an error.
    """
    if not cursor:
        return None
    try:
        written, last_id = base64.urlsafe_b64decode(cursor).decode().split("|")
        moment = parse_datetime(written)
        return (moment, int(last_id)) if moment else None
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
