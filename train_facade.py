import datetime
import logging
import os
from datetime import date

import dateutil
import requests
from dateutil.parser import parse

from date_utils import next_weekday

RAIL_API_ENDPOINT = 'https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation={from_station}&toStation={to_station}&date' \
                    '={day}&hour={hour}&scheduleType=1&systemType=1&language"id"="hebrew"'
RAIL_API_KEY = os.environ['RAIL_TOKEN']


def get_train_times(departure_station, arrival_station, day_num=None):
    day = date.today() if day_num is None else next_weekday(date.today(), day_num)
    current_hour = '16:30'
    res = get_timetable(departure_station, arrival_station, day, current_hour)
    return [(travel['departureTime'], travel['arrivalTime']) for travel in res['result']['travels']]


def get_timetable(departure_station, arrival_station, day, hour):
    uri = RAIL_API_ENDPOINT.format(from_station=departure_station, to_station=arrival_station, day=day,
                                   hour=hour)
    response = requests.get(uri, headers={
        "Accept": "application/json",
        "Ocp-Apim-Subscription-Key": RAIL_API_KEY,
    })
    logging.debug(response)
    res = response.json()
    return res


class TrainTimes:
    def __init__(self, original_departure, original_arrival, delay_in_minutes):
        self.original_departure = original_departure
        self.original_arrival = original_arrival
        self.delay_in_minutes = delay_in_minutes

    def get_updated_departure(self):
        return parse(self.original_departure) + datetime.timedelta(minutes=self.delay_in_minutes)

    def get_updated_arrival(self):
        return parse(self.original_arrival) + datetime.timedelta(minutes=self.delay_in_minutes)


class TrainNotFoundError:
    pass


def get_delay_from_api(from_station, to_station, hour) -> TrainTimes:
    logging.info("Checking for delays for train from {} to {} at {} today".format(from_station, to_station, hour))
    day = dateutil.parser.isoparse(hour).date()
    # Format in specific train '2023-09-17T21:55:00'
    # Format in sub:
    timetable = get_timetable(from_station, to_station, day, '07:00')
    for travel in timetable['result']['travels']:
        scheduled_departure = travel['departureTime']
        if scheduled_departure != hour:
            continue

        train_position = travel['trains'][0]['trainPosition']
        original_departure = travel['departureTime']
        original_arrival = travel['arrivalTime']

        if train_position is None:
            logging.info('No info for train departing at {departure}, it is probably on time'.format(departure=scheduled_departure))
            return TrainTimes(original_departure, original_arrival, 0)

        train_delay = train_position['calcDiffMinutes']

        train_times = TrainTimes(hour, original_arrival, train_delay)
        logging.debug('Original Departure: {origDep}, delay: {delay}, updated departure: {updated_departure}'.format(
            origDep=scheduled_departure, delay=train_delay, updated_departure=train_times.get_updated_departure()))

        return train_times
    raise TrainNotFoundError

