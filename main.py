import logging
import os

from notification_scheduler import schedule_train_notification
from rail_bot import start_bot

# https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation=4600&toStation=7300&date=2023-05-23&hour=16:30&scheduleType=1&systemType=1&language"id"="hebrew"

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_TOKEN']

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.info("Starting")

    # My user id 427475755
    # delay = get_delay_from_api('7320', '4600', '07:28')

    schedule_train_notification('427475755', '7320', '4600', '07:28', 'mon', 4, 00)
    schedule_train_notification('427475755', '7320', '4600', '07:41', 'mon', 4, 00)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'mon', 13, 15)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'mon', 13, 29)

    schedule_train_notification('427475755', '7320', '4600', '07:28', 'wed', 4, 00)
    schedule_train_notification('427475755', '7320', '4600', '07:41', 'wed', 4, 00)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'wed', 13, 15)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'wed', 13, 29)

    start_bot(TELEGRAM_BOT_TOKEN)
