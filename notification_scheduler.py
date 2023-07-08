import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from rail_bot import send_status_notification

# scheduler = AsyncIOScheduler(jobstores={'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')})
scheduler = AsyncIOScheduler(jobstores={'default': SQLAlchemyJobStore(url='sqlite:///:memory:')},
                             timezone='Israel')
scheduler.start()


async def send_notification_for_specific_train_user(chat_id: str, from_station: str, to_station: str, train_time: str):
    logging.info("Checking for details for chat id %s, train from %s to %s on %s", chat_id, from_station,
                 to_station, train_time)
    await send_status_notification(chat_id, from_station, to_station, train_time)


def schedule_train_notification(chat_id: str, from_station: str, to_station: str, train_time: str,
                                day_of_week: str,
                                notification_hour: int, notification_minute: int):
    context = {'chat_id': chat_id, 'from_station': from_station, 'to_station': to_station, 'train_time': train_time}

    job = scheduler.add_job(send_notification_for_specific_train_user, 'cron', day_of_week=day_of_week,
                            hour=notification_hour, minute=notification_minute, kwargs=context)

    logging.info("Scheduled job %s", job)
    return job


def await_termination():
    print("jobs:")
    print(scheduler.get_jobs())
    scheduler.shutdown()
