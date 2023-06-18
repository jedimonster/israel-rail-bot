import logging
import time

from notification_scheduler import schedule_train_notification, await_termination
from rail_bot import start_bot
from train_facade import get_train_times, get_delay_from_api

# https://israelrail.azurefd.net/rjpa-prod/api/v1/timetable/searchTrainLuzForDateTime?fromStation=4600&toStation=7300&date=2023-05-23&hour=16:30&scheduleType=1&systemType=1&language"id"="hebrew"

TELEGRAM_BOT_TOKEN = '6225246636:AAG842217K8ILQJ5Pg_RHWXf8VcuSdv8NhQ'
RAIL_API_KEY = '4b0d355121fe4e0bb3d86e902efe9f20'

LOG_FORMAT = '%(asctime)s %(levelname)s %(message)s'

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.info("Starting")

    # My user id 427475755
    delay = get_delay_from_api('7320', '4600', '07:28')

    schedule_train_notification('427475755', '7320', '4600', '07:28', 'sun', 7, 00)
    schedule_train_notification('427475755', '7320', '4600', '07:41', 'sun', 11, 00)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'sun', 16, 15)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'sun', 16, 29)
    schedule_train_notification('427475755', '4600', '7320', '17:15', 'sun', 16, 15)

    schedule_train_notification('427475755', '7320', '4600', '07:28', 'mon', 7, 00)
    schedule_train_notification('427475755', '7320', '4600', '07:41', 'mon', 11, 00)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'mon', 16, 15)
    schedule_train_notification('427475755', '4600', '7320', '16:45', 'mon', 16, 29)
    schedule_train_notification('427475755', '4600', '7320', '17:15', 'mon', 16, 15)



    start_bot()
