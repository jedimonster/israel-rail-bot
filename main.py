import logging
import os

from database import create_tables
from rail_bot import start_bot

# https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation=4600&toStation=7300&date=2023-05-23&hour=16:30&scheduleType=1&systemType=1&language"id"="hebrew"

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_TOKEN']

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.info("Starting")

    create_tables()

    start_bot(TELEGRAM_BOT_TOKEN)
