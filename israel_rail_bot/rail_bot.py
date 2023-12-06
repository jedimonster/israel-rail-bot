import json
import logging
from datetime import datetime, timedelta, date
from itertools import groupby
from typing import Optional

import dateutil
import humanize
from apscheduler.jobstores.base import JobLookupError
from dateutil.parser import parse
from telegram import Update, InlineKeyboardMarkup, \
    InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, \
    CallbackContext, ExtBot, PicklePersistence

import notification_scheduler
from database import add_subscription_to_database, get_subscriptions, TrainSubscription, get_subscription, \
    delete_subscriptions
from date_utils import next_weekday, WEEKDAYS
from train_facade import get_train_times, get_delay_from_api, TrainNotFoundError, station_id_to_name
from train_stations import FAVORITE_TRAIN_STATIONS

FROM_STATION_KEY = 'from_station'
TO_STATION_KEY = 'to_station'
TIME_KEY = 'time'
DAY_KEY = 'day'

SELECTED_ID = 'si'
NEXT_STATE = 'ns'

SELECT_ARRIVAL_STATION = 'SELECT_ARRIVAL_STATION'
SELECT_DEPARTURE_TIME = 'SELECT_DEPARTURE_TIME'
SELECT_DEPARTURE_STATION = 'SELECT_DEPARTURE_STATION'
CHECK_DELAYS_FOR_SPECIFIC_TIME = 'CHECK_DELAYS_FOR_SPECIFIC_TIME'
REFRESH = 'REFRESH'
SUBSCRIBE_TO_SPECIFIC = 'SUBSCRIBE_TO_SPECIFIC'

SELECT_TRAIN_VARIANT_KEY = 'train_variant'
SELECT_TRAIN_VARIANT_IN_FLIGHT = 'in_flight'
SELECT_TRAIN_VARIANT_FUTURE = 'future'
SUBSCRIBE_VARIANT = 'subscribe'

LIST_SUBSCRIPTION = 'LIST_SUBSCRIPTION'
EDIT_SUBSCRIPTION = 'EDIT_SUBSCRIPTION'
DELETE_SUBSCRIPTION = 'DELETE_SUBSCRIPTION'
CHECK_SUBSCRIPTION = 'CHECK_SUBSCRIPTION'
SUB_ID = 'SUB_ID'

bot = None


def next_state_is(state):
    def is_state(data):
        d = json.loads(data)
        return d[NEXT_STATE] == state

    return is_state


async def bot_error_handler(update: Optional[object], context: CallbackContext):
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update is not None:
        try:
            await update.effective_message.edit_text("Sorry, something went wrong.")
        except:
            await update.message.reply_text("Sorry, something went wrong")


def start_sender_bot(token):
    global bot
    bot = ExtBot(token)


def start_bot(token):
    application = ApplicationBuilder().persistence(
        PicklePersistence(filepath='../bot_data.pickle')).arbitrary_callback_data(True).token(token).build()

    application.add_error_handler(bot_error_handler)

    application.add_handler(CommandHandler("check_specific_train", check_specific_train))
    application.add_handler(
        CallbackQueryHandler(select_arrival_station, next_state_is(SELECT_ARRIVAL_STATION), block=False))
    application.add_handler(
        CallbackQueryHandler(select_departure_time, next_state_is(SELECT_DEPARTURE_TIME), block=False))
    application.add_handler(
        CallbackQueryHandler(check_delays_for_specific_time, next_state_is(CHECK_DELAYS_FOR_SPECIFIC_TIME),
                             block=False))
    application.add_handler(CommandHandler("check_in_flight_train", check_in_flight_train))
    application.add_handler(
        CallbackQueryHandler(check_delays_for_specific_time, next_state_is(REFRESH),
                             block=False))
    application.add_handler(
        CallbackQueryHandler(check_delays_for_specific_time, next_state_is(SUBSCRIBE_TO_SPECIFIC), block=False))

    application.add_handler(CommandHandler("subscribe", subscribe_to_train))
    application.add_handler(
        CallbackQueryHandler(save_day_and_show_departure_buttons, next_state_is(SELECT_DEPARTURE_STATION), block=False))

    application.add_handler(CommandHandler("subscriptions", list_subscriptions))
    application.add_handler(CallbackQueryHandler(list_subscriptions, next_state_is(LIST_SUBSCRIPTION), block=False))
    application.add_handler(CallbackQueryHandler(edit_subscription, next_state_is(EDIT_SUBSCRIPTION), block=False))
    application.add_handler(CallbackQueryHandler(delete_subscription, next_state_is(DELETE_SUBSCRIPTION), block=False))
    application.add_handler(CallbackQueryHandler(check_subscription, next_state_is(CHECK_SUBSCRIPTION), block=False))

    application.run_polling()


async def check_in_flight_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_deparature_buttons(update, context, {SELECT_TRAIN_VARIANT_KEY: SELECT_TRAIN_VARIANT_IN_FLIGHT})


async def check_specific_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_deparature_buttons(update, context, {SELECT_TRAIN_VARIANT_KEY: SELECT_TRAIN_VARIANT_FUTURE})


async def subscribe_to_train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_day_selection(update, context, {SELECT_TRAIN_VARIANT_KEY: SUBSCRIBE_VARIANT})


async def show_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, additional_ctx=None):
    buttons = [[InlineKeyboardButton(day.name, callback_data=json.dumps({
                                                                            NEXT_STATE: SELECT_DEPARTURE_STATION,
                                                                            DAY_KEY: day.value
                                                                        } | additional_ctx))] for day in WEEKDAYS]

    await update.message.reply_text("Please select subscription day:", reply_markup=InlineKeyboardMarkup(buttons))


async def save_day_and_show_departure_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, additional_ctx=None):
    callback_data = json.loads(update.callback_query.data)
    callback_data.pop(NEXT_STATE)
    await show_deparature_buttons(update, context, callback_data)


async def show_deparature_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, additional_ctx=None):
    if additional_ctx is None:
        additional_ctx = {}
    logging.info("Got select_departure_station command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    # Get the user's selected departure stations
    buttons = get_station_buttons(FAVORITE_TRAIN_STATIONS, SELECT_ARRIVAL_STATION, FROM_STATION_KEY, additional_ctx)

    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query is not None and update.callback_query.message is not None:
        await update.callback_query.message.edit_text("Please select a departure station:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Please select a departure station:", reply_markup=reply_markup)

    return "select_arrival_station"


def get_station_buttons(stations, next_state, ctx_key_for_station, additional_context=None):
    if additional_context is None:
        additional_context = {}
    if 'ns' in additional_context:
        additional_context.pop('ns')
    stations = sorted(stations, key=lambda station: station['english'])
    return [[InlineKeyboardButton(station['english'], callback_data=json.dumps({
                                                                                   NEXT_STATE: next_state,
                                                                                   ctx_key_for_station: station['id']
                                                                               } | additional_context))]
            for station in stations]


async def select_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_arrival_station command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    callback_data = json.loads(update.callback_query.data)
    departure_station_id = callback_data[FROM_STATION_KEY]

    # Get the user's selected departure stations
    additional_context = {FROM_STATION_KEY: departure_station_id} | callback_data
    buttons = get_station_buttons(list(filter(lambda station: station['id'] != departure_station_id, FAVORITE_TRAIN_STATIONS)),
                                  SELECT_DEPARTURE_TIME, TO_STATION_KEY, additional_context)

    reply_markup = InlineKeyboardMarkup(buttons)
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, FAVORITE_TRAIN_STATIONS))['english'].replace(
        '-', '\-')

    await update.callback_query.message.edit_text(
        'Departing from *{departure_station}*\. Select arrival station:'.format(
            departure_station=departure_station_name), reply_markup=reply_markup, parse_mode='MarkdownV2')

    return "stations_selected"


def format_time_from_str(t, show_day=True):
    request_time = dateutil.parser.isoparse(t)

    return format_time(request_time, show_day)


def format_time(request_time, show_day=True):
    natural_date = humanize.naturalday(request_time)
    absolute_time = datetime.strftime(request_time, '%H:%M')
    if show_day and request_time.date() != datetime.now().date():
        return "{date} at {time}".format(date=natural_date, time=absolute_time)
    else:
        return absolute_time


def fmt_interval(dep, arr):
    delta = dateutil.parser.isoparse(arr) - dateutil.parser.isoparse(dep)

    m = int(delta.seconds / 60)
    if (m >= 60):
        h = int(m / 60)
        m = m % 60
    else:
        h = 0
    if (h == 0):
        return "{m}m".format(m=m)
    else:
        return "{h}h:{m}m".format(h=h, m=m)


async def select_departure_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_departure_time command from user=%s, context=%s, chat_id=%s", update.effective_user,
                 context.chat_data, update.effective_chat.id)

    query = update.callback_query
    callback_data = json.loads(update.callback_query.data)

    logging.info("Callback data %s", callback_data)

    to_station_id = callback_data[TO_STATION_KEY]
    from_station_id = callback_data[FROM_STATION_KEY]
    callback_data.pop('ns')

    additional_context = {FROM_STATION_KEY: from_station_id, TO_STATION_KEY: to_station_id} | callback_data

    day = callback_data[DAY_KEY] if DAY_KEY in callback_data else None
    all_times = get_train_times(from_station_id,
                                to_station_id, day)
    now = datetime.now()

    train_variant = callback_data[SELECT_TRAIN_VARIANT_KEY]
    logging.info("Checking train variant %s", train_variant)

    def is_applicable_time(time):
        (departure_time, arrival_time, switches) = time
        if train_variant == SELECT_TRAIN_VARIANT_FUTURE:
            return dateutil.parser.isoparse(departure_time) > now
        elif train_variant == SELECT_TRAIN_VARIANT_IN_FLIGHT:
            return dateutil.parser.isoparse(departure_time) < now < dateutil.parser.isoparse(arrival_time)
        elif train_variant == SUBSCRIBE_VARIANT:
            return True

    relevant_times = list(filter(is_applicable_time,
                                 all_times))

    time_by_hour_iter = groupby(relevant_times, lambda time: (
        dateutil.parser.isoparse(time[0]).hour))

    time_by_hour = []

    for hour, hourtimes in time_by_hour_iter:
        time_by_hour.append(list(hourtimes))

    buttons = [[
        InlineKeyboardButton(
            "{dep} ({duration}) {switch_indicator}".format(dep=format_time_from_str(dep, show_day=False),
                                                           switch_indicator=fmt_switch_indicator(switches),
                                                           duration=fmt_interval(dep, arr)).capitalize(),
            callback_data=json.dumps({'ns': CHECK_DELAYS_FOR_SPECIFIC_TIME, TIME_KEY: dep} | additional_context))
        for dep, arr, switches in times] for times in time_by_hour]

    reply_markup = InlineKeyboardMarkup(buttons)

    departure_station_name = station_id_to_name(from_station_id)
    arrival_station_name = station_id_to_name(to_station_id)

    await query.message.edit_text(
        "Departing from *{departure_station}* to *{arrival_station}*\. Please select departure time:".format(
            departure_station=departure_station_name, arrival_station=arrival_station_name), reply_markup=reply_markup,
        parse_mode='MarkdownV2')

    return "departure_time_selected"


def fmt_switch_indicator(switches):
    if switches > 0:
        return '*'
    return ''


async def check_delays_for_specific_time(update: Update, context: ContextTypes.DEFAULT_TYPE, to_user=None):
    logging.info("Got departure_time_selected command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    query = update.callback_query
    callback_data = json.loads(query.data)
    logging.info("Callback data %s", callback_data)

    selected_time = callback_data['time']
    departure_station_id = callback_data[FROM_STATION_KEY]
    arrival_station_id = callback_data[TO_STATION_KEY]

    if SELECT_TRAIN_VARIANT_KEY in callback_data and callback_data[SELECT_TRAIN_VARIANT_KEY] == SUBSCRIBE_VARIANT:
        logging.info("Subscribing to train")
        chat_id = update.effective_chat.id
        dt = dateutil.parser.isoparse(selected_time)
        selected_hour = dt.strftime("%H:%M")
        notification_time = dt - timedelta(minutes=30)

        selected_day_num = int(dt.strftime('%w'))
        scheduled_job = notification_scheduler.schedule_train_notification(str(chat_id), departure_station_id,
                                                                           arrival_station_id,
                                                                           selected_hour,
                                                                           selected_day_num,
                                                                           notification_time.hour,
                                                                           notification_time.minute)

        add_subscription_to_database(chat_id, departure_station_id, arrival_station_id, WEEKDAYS(selected_day_num).name,
                                     selected_hour,
                                     scheduled_job.id)
        await query.message.edit_text(
            "I've subscribed you to the 🚆 {from_station} \- {to_station} train service departing {day} at "
            "⏰ {departure_time}\. I'll provide a status update 30 minutes before departure\.".format(
                day=WEEKDAYS(selected_day_num).name,
                from_station=station_id_to_name(callback_data[FROM_STATION_KEY]),
                to_station=station_id_to_name(callback_data[TO_STATION_KEY]), departure_time=selected_hour),
            parse_mode='MarkdownV2')
        return

    logging.info("Checking delay from %s to %s on %s", departure_station_id, arrival_station_id, selected_time)

    train_times = get_delay_from_api(departure_station_id,
                                     arrival_station_id, selected_time)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Refresh", callback_data=json.dumps(
            {NEXT_STATE: REFRESH, FROM_STATION_KEY: departure_station_id, TO_STATION_KEY: arrival_station_id,
             TIME_KEY: selected_time})),
          InlineKeyboardButton("Subscribe", callback_data=json.dumps(
              {
                  NEXT_STATE: SUBSCRIBE_TO_SPECIFIC,
                  SELECT_TRAIN_VARIANT_KEY: SUBSCRIBE_VARIANT,
                  FROM_STATION_KEY: departure_station_id,
                  TO_STATION_KEY: arrival_station_id,
                  TIME_KEY: selected_time}))]])

    response_txt = format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id)

    if to_user is None:
        await query.message.edit_text(response_txt, parse_mode='MarkdownV2', reply_markup=reply_markup)
    else:
        pass

    return ConversationHandler.END


def format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id):
    departure_station_name = station_id_to_name(departure_station_id)
    arrival_station_name = station_id_to_name(arrival_station_id)
    last_update_str = '\(updated {}\)'.format(datetime.strftime(datetime.now(), '%H:%M'))
    if train_times.delay_in_minutes > 0:
        departure_str = '️️~{}~ ⏱ {}'.format(format_time_from_str(train_times.original_departure),
                                             format_time(train_times.get_updated_departure(), False))
        arrival_str = '{}'.format(format_time(train_times.get_updated_arrival(), False))
    else:
        departure_str = '✅ {}'.format(format_time(train_times.get_updated_departure()))
        arrival_str = format_time_from_str(train_times.original_arrival, False)

    if train_times.switch_stations is not None:
        switches = 'You will have to switch at: ' + ','.join(train_times.switch_stations) + '\n'
    else:
        switches = ''
    resposne_txt = "From: *{departure_station}* \n" \
                   "To: *{arrival_station}*\n" \
                   "Departing: *{departure_str}*\n" \
                   "Will arrive at {arrival_str}\. \n" \
                   "{switches}" \
                   "{updated}".format(
        departure_station=departure_station_name, arrival_station=arrival_station_name,
        departure_str=departure_str, arrival_str=arrival_str, updated=last_update_str, switches=switches)
    return resposne_txt


async def send_status_notification(chat_id, from_station, to_station, train_day: int, train_hour: str):
    hour, minute = map(int, train_hour.split(':'))
    day = next_weekday(date.today(), train_day)
    train_datetime = datetime(year=day.year, month=day.month, day=day.day, hour=hour, minute=minute,
                              second=0).isoformat(timespec='seconds')
    try:
        train_times = get_delay_from_api(from_station, to_station, train_datetime)
    except TrainNotFoundError:
        logging.info("Could not find the train from {} to {} day {} hour {} datetime {}", from_station, to_station,
                     train_day,
                     train_hour, train_datetime)
        await bot.send_message(chat_id, "From: *{}*\n"
                                        "To: *{}*\n"
                                        "Departing at *{}* appears to be ❌ *CANCELED*".format(
            station_id_to_name(from_station), station_id_to_name(to_station), format_time_from_str(train_datetime)),
                               parse_mode='MarkdownV2')
        return
    response_txt = format_delay_response(train_times, train_datetime, from_station, to_station)
    logging.info("Sending delay notification to chat_id %s", chat_id)
    await bot.send_message(chat_id, response_txt, parse_mode='MarkdownV2')


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscriptions: [TrainSubscription] = get_subscriptions(str(chat_id))
    buttons = [[InlineKeyboardButton(
        "{} {} {} - {}".format(sub.day_of_week, sub.train_hour, station_id_to_name(sub.from_station, False),
                               station_id_to_name(sub.to_station, False)), callback_data=json.dumps({
            NEXT_STATE: EDIT_SUBSCRIPTION,
            SUB_ID: sub.id
        }))] for sub in
        subscriptions]

    message = update.message if update.message is not None else update.callback_query.message
    if not buttons:
        await message.reply_text("No active subscriptions. To add a subscription, type /subscribe")
        return
    if update.message is not None:
        await message.reply_text("Active subscriptions:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.callback_query.message.edit_text("Active subscriptions:",
                                                      reply_markup=InlineKeyboardMarkup(buttons))


async def edit_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_data = json.loads(update.callback_query.data)
    sub_id = callback_data[SUB_ID]
    chat_id = update.effective_chat.id
    sub = get_subscription(str(chat_id), sub_id)

    buttons = [
        [
            InlineKeyboardButton("Check now", callback_data=json.dumps({
                NEXT_STATE: CHECK_SUBSCRIPTION,
                SUB_ID: sub_id,
            })),
            InlineKeyboardButton("Delete", callback_data=json.dumps({
                NEXT_STATE: DELETE_SUBSCRIPTION,
                SUB_ID: sub_id
            }))],
        [
            InlineKeyboardButton("<< Back to subscriptions", callback_data=json.dumps({
                NEXT_STATE: LIST_SUBSCRIPTION,
            }))]]

    sub_desc = "Subscription on {}, {} from {} to {}".format(sub.day_of_week, sub.train_hour,
                                                             station_id_to_name(sub.from_station),
                                                             station_id_to_name(sub.to_station))
    await update.callback_query.message.edit_text(sub_desc, reply_markup=InlineKeyboardMarkup(buttons),
                                                  parse_mode='MarkdownV2')


async def delete_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_data = json.loads(update.callback_query.data)
    sub_id = callback_data[SUB_ID]
    chat_id = str(update.effective_chat.id)
    sub = get_subscription(chat_id, sub_id)

    try:
        notification_scheduler.delete_job(sub.scheduler_job_id)
    except JobLookupError:
        logging.warning("Could not find job id %s", sub.scheduler_job_id)

    delete_subscriptions(sub_id)

    await update.callback_query.message.edit_text("Deleted subscription")
    await list_subscriptions(update, context)


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_data = json.loads(update.callback_query.data)
    sub_id = callback_data[SUB_ID]
    chat_id = str(update.effective_chat.id)
    sub = get_subscription(chat_id, sub_id)

    await send_status_notification(sub.chat_id, sub.from_station, sub.to_station, WEEKDAYS[sub.day_of_week],
                                   sub.train_hour)
