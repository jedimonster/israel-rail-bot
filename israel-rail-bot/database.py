import logging
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

from date_utils import WEEKDAYS


class Base(DeclarativeBase):
    pass


@dataclass
class TrainSubscription(Base):
    __tablename__ = 'train_subscriptions'

    from_station: Mapped[int]
    to_station: Mapped[int]
    train_hour: Mapped[str]
    day_of_week: Mapped[str]
    scheduler_job_id: Mapped[str]
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column()


sqlalchemy_engine = create_engine("sqlite+pysqlite:///subscriptions.sqlite", echo=False)


def create_tables():
    Base.metadata.create_all(sqlalchemy_engine)


def add_subscription_to_database(chat_id, departure_station_id, arrival_station_id, selected_day, selected_time,
                                 scheduler_job_id):
    with Session(sqlalchemy_engine) as session:
        train_sub = TrainSubscription(
            chat_id=chat_id,
            from_station=departure_station_id,
            to_station=arrival_station_id,
            train_hour=selected_time,
            day_of_week=selected_day,
            scheduler_job_id=scheduler_job_id
        )
        session.add(train_sub)
        session.commit()

    with Session(sqlalchemy_engine) as session:
        select_subs = select(TrainSubscription).where(TrainSubscription.chat_id == chat_id)
        subs = session.scalars(select_subs).all()
        logging.info("Active user subs: %s", subs)


def get_subscriptions(chat_id: str) -> [TrainSubscription]:
    with Session(sqlalchemy_engine) as session:
        statement = select(TrainSubscription).where(TrainSubscription.chat_id == chat_id).order_by(
            TrainSubscription.day_of_week, TrainSubscription.train_hour)
        train_subs = session.scalars(statement).all()

        def extract_weekday(sub: TrainSubscription):
            return WEEKDAYS[sub.day_of_week].value
        train_subs = sorted(train_subs, key=extract_weekday)

    return train_subs


def get_subscription(chat_id: str, sub_id: str) -> [TrainSubscription]:
    with Session(sqlalchemy_engine) as session:
        statement = select(TrainSubscription).where(TrainSubscription.chat_id == chat_id,
                                                    TrainSubscription.id == sub_id)
        train_sub = session.scalar(statement)

    return train_sub


def delete_subscriptions(sub_id):
    with Session(sqlalchemy_engine) as session:
        sub = session.get(TrainSubscription, sub_id)
        session.delete(sub)
        session.commit()


if __name__ == '__main__':
    pass
