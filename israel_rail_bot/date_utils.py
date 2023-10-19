import datetime
from enum import IntEnum


def next_weekday(d: datetime.date, weekday: int):
    d_weekday = d.weekday() + 1  # account for the week starting on Sunday.
    days_ahead = weekday - d_weekday
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


WEEKDAYS = IntEnum("Weekdays", 'Sunday Monday Tuesday Wednesday Thursday Friday Saturday', start=0)
