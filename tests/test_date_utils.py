import datetime
import unittest

from assertpy import assert_that

from israel_rail_bot.date_utils import next_weekday


class NextWeekDayTestCase(unittest.TestCase):
    def test_same_sunday(self):
        sunday_date = datetime.date(2023, 10, 15)
        sunday_idx = 0

        actual_date = next_weekday(sunday_date, sunday_idx)
        assert_that(actual_date).is_equal_to(sunday_date)

    def test_same_weekday(self):
        wednesday_date = datetime.date(2023, 10, 18)
        wednesday_idx = 3

        actual_date = next_weekday(wednesday_date, wednesday_idx)
        assert_that(actual_date).is_equal_to(wednesday_date)

    def test_next_weekday(self):
        monday_date = datetime.date(2023, 10, 16)
        sunday_idx = 0

        actual_date = next_weekday(monday_date, sunday_idx)
        next_sunday = datetime.date(2023, 10, 22)
        assert_that(actual_date).is_equal_to(next_sunday)


if __name__ == '__main__':
    unittest.main()
