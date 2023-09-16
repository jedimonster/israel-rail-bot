import datetime
from enum import IntEnum


def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)


WEEKDAYS = IntEnum("Weekdays", 'Monday Tuesday Wednesday Thursday Friday Saturday', start=0)
