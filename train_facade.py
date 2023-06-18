import datetime
import logging
import os
from datetime import date
import requests
from dateutil.parser import parse

RAIL_API_ENDPOINT = 'https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation={from_station}&toStation={to_station}&date' \
                    '={day}&hour={hour}&scheduleType=1&systemType=1&language"id"="hebrew"'
RAIL_API_KEY = os.environ['RAIL_TOKEN']


def get_train_times(departure_station, arrival_station):
    day = date.today()
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


def get_delay_from_api(from_station, to_station, hour):
    day = date.today()
    res = get_timetable(from_station, to_station, day, '07:00')
    for travel in res['result']['travels']:
        scheduled_departure = travel['departureTime']
        if scheduled_departure != hour:
            continue

        train_position = travel['trains'][0]['trainPosition']
        if train_position is None:
            logging.info('No info for train departing at {departure}'.format(departure=scheduled_departure))
            continue

        train_delay = train_position['calcDiffMinutes']
        updated_departure = parse(scheduled_departure) + datetime.timedelta(minutes=train_delay)
        logging.debug('Original Departure: {origDep}, delay: {delay}, updated departure: {updated_departure}'.format(
            origDep=scheduled_departure, delay=train_delay, updated_departure=updated_departure))

        if train_delay > 0:
            return train_delay
