import json
import logging
from datetime import datetime
from itertools import groupby
from typing import Optional

import dateutil
import humanize
from dateutil.parser import parse
from telegram import Update, InlineKeyboardMarkup, \
    InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, \
    CallbackContext, CallbackDataCache, ExtBot

from train_facade import get_train_times, get_delay_from_api
from train_stations import TRAIN_STATIONS

FROM_STATION_KEY = 'from_station'
TO_STATION_KEY = 'to_station'
SELECTED_STATION_KEY = 'selected_station'
TIME_KEY = 'time'

SELECTED_ID = 'si'
NEXT_STATE = 'ns'

SELECT_ARRIVAL_STATION = 'c1'
SELECT_DEPARTURE_TIME = 'c2'
CHECK_DELAYS_FOR_SPECIFIC_TIME = 'c3'
REFRESH = 'c4'
SUBSCRIBE_TO_SPECIFIC = 'c5'

bot = None
callback_data_cache: CallbackDataCache | None = None


def next_state_is(state):
    def is_state(data):
        d = json.loads(data)
        return d['ns'] == state

    return is_state


async def bot_error_handler(update: Optional[object], context: CallbackContext):
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update is not None:
        await update.effective_message.edit_text("Sorry, something went wrong.")
        # await update.effective_message.reply_text("Sorry, something went wrong.")


def start_bot(token):
    global bot, callback_data_cache
    bot = ExtBot(token)
    # await bot.initialize()
    # callback_data_cache = CallbackDataCache(bot)
    # callback_data_cache = bot.callback_data_cache
    application = ApplicationBuilder().arbitrary_callback_data(True).token(token).build()

    application.add_error_handler(bot_error_handler)

    application.add_handler(CommandHandler("check_specific_train", select_departure_station))
    application.add_handler(
        CallbackQueryHandler(select_arrival_station, next_state_is(SELECT_ARRIVAL_STATION), block=False))
    application.add_handler(
        CallbackQueryHandler(select_departure_time, next_state_is(SELECT_DEPARTURE_TIME), block=False))
    application.add_handler(
        CallbackQueryHandler(check_delays_for_specific_time, next_state_is(CHECK_DELAYS_FOR_SPECIFIC_TIME),
                             block=False))

    application.run_polling()


async def select_departure_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_departure_station command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    # Get the user's selected departure stations
    buttons = get_station_buttons(TRAIN_STATIONS, SELECT_ARRIVAL_STATION)

    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("Please select a departure station:", reply_markup=reply_markup)

    return "select_arrival_station"


def get_station_buttons(stations, next_state, additional_context={}):
    stations = sorted(stations, key=lambda station: station['english'])
    return [[InlineKeyboardButton(station['english'], callback_data=json.dumps({
                                                                                   NEXT_STATE: next_state,
                                                                                   SELECTED_STATION_KEY: station['id']
                                                                               } | additional_context))]
            for station in stations]


async def select_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_arrival_station command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    callback_data = json.loads(update.callback_query.data)
    departure_station_id = callback_data[SELECTED_STATION_KEY]
    # context.chat_data['departure_station_id'] = departure_station_id

    # Get the user's selected departure stations
    additional_context = {FROM_STATION_KEY: departure_station_id}
    buttons = get_station_buttons(list(filter(lambda station: station['id'] != departure_station_id, TRAIN_STATIONS)),
                                  SELECT_DEPARTURE_TIME, additional_context)

    reply_markup = InlineKeyboardMarkup(buttons)
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, TRAIN_STATIONS))['english'].replace(
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
    # callback_data_cache.process_callback_query(query)
    callback_data = json.loads(update.callback_query.data)

    logging.info("Callback data %s", callback_data)

    to_station_id = callback_data[SELECTED_STATION_KEY]
    # context.chat_data['arrival_station_id'] = to_station_id
    # from_station_id = context.chat_data['from_station_id']
    from_station_id = callback_data[FROM_STATION_KEY]

    additional_context = {FROM_STATION_KEY: from_station_id, TO_STATION_KEY: to_station_id}

    all_times = get_train_times(from_station_id,
                                to_station_id)
    now = datetime.now()

    def is_applicable_time(time):
        (dep, arr) = time
        return dateutil.parser.isoparse(arr) > now

    future_times = list(filter(is_applicable_time,
                               all_times))

    time_by_hour_iter = groupby(future_times, lambda time: (
        dateutil.parser.isoparse(time[0]).hour))

    time_by_hour = []

    for hour, hourtimes in time_by_hour_iter:
        time_by_hour.append(list(hourtimes))

    buttons = [[
        InlineKeyboardButton(
            "{dep} ({duration})".format(dep=format_time_from_str(dep, show_day=False),
                                        duration=fmt_interval(dep, arr)).capitalize(),
            callback_data=json.dumps({'ns': CHECK_DELAYS_FOR_SPECIFIC_TIME, TIME_KEY: dep} | additional_context))
        for dep, arr in times] for times in time_by_hour]

    reply_markup = InlineKeyboardMarkup(buttons)
    # reply_markup = callback_data_cache.process_keyboard(reply_markup)


    departure_station_name = next(filter(lambda s: s['id'] == from_station_id, TRAIN_STATIONS))['english'].replace(
        '-', '\-')
    arrival_station_name = next(filter(lambda s: s['id'] == to_station_id, TRAIN_STATIONS))['english'].replace(
        '-', '\-')

    await query.message.edit_text(
        "Departing from *{departure_station}* to *{arrival_station}*\. Please select departure time:".format(
            departure_station=departure_station_name, arrival_station=arrival_station_name), reply_markup=reply_markup,
        parse_mode='MarkdownV2')

    return "departure_time_selected"


async def check_delays_for_specific_time(update: Update, context: ContextTypes.DEFAULT_TYPE, to_user=None):
    logging.info("Got departure_time_selected command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    query = update.callback_query
    # callback_data_cache.process_callback_query(callback_query=query)
    callback_data = json.loads(query.data)
    logging.info("Callback data %s", callback_data)

    selected_time = callback_data['time']
    departure_station_id = callback_data[FROM_STATION_KEY]
    arrival_station_id = callback_data[TO_STATION_KEY]

    logging.info("Checking delay from %s to %s on %s", departure_station_id, arrival_station_id, selected_time)

    train_times = get_delay_from_api(departure_station_id,
                                     arrival_station_id, selected_time)

    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Refresh", callback_data=json.dumps(
            {NEXT_STATE: REFRESH, FROM_STATION_KEY: departure_station_id, TO_STATION_KEY: arrival_station_id,
             TIME_KEY: selected_time})),
          InlineKeyboardButton("Subscribe", callback_data=json.dumps(
              {NEXT_STATE: SUBSCRIBE_TO_SPECIFIC, FROM_STATION_KEY: departure_station_id,
               TO_STATION_KEY: arrival_station_id, TIME_KEY: selected_time}))]])

    # reply_markup = callback_data_cache.process_keyboard(reply_markup)

    response_txt = format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id)

    if to_user is None:
        await query.message.edit_text(response_txt, parse_mode='MarkdownV2', reply_markup=reply_markup)
    else:
        pass

    return ConversationHandler.END


def format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id):
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, TRAIN_STATIONS))['english'].replace(
        '-', '\-')
    arrival_station_name = next(filter(lambda s: s['id'] == arrival_station_id, TRAIN_STATIONS))['english'].replace('-',
                                                                                                                    '\-')
    last_update_str = '(updated {})'.format(datetime.strftime(datetime.now(), '%H:%M'))
    if train_times.delay_in_minutes > 0:
        # delay_str = "is ⏱️ {delay} minutes late".format(delay=str(train_times))
        departure_str = '️️~{}~ ⏱ {}'.format(format_time_from_str(train_times.original_departure),
                                             format_time(train_times.get_updated_departure(), False))
        arrival_str = '{}'.format(format_time(train_times.get_updated_arrival(), False))
    else:
        departure_str = '✅ {}'.format(format_time(train_times.get_updated_departure()))
        arrival_str = format_time_from_str(train_times.original_arrival, False)
    resposne_txt = "Train from {departure_station} to {arrival_station} " \
                   "Departing *{departure_str}* will arrive at {arrival_str}\.".format(
        departure_station=departure_station_name, arrival_station=arrival_station_name,
        departure_str=departure_str, arrival_str=arrival_str)
    return resposne_txt


async def send_status_notification(chat_id, from_station, to_station, train_hour: str):
    hour, minute = map(int, train_hour.split(':'))
    train_datetime = datetime.now().replace(hour=hour, minute=minute).isoformat()
    train_times = get_delay_from_api(from_station, to_station, train_hour)
    response_txt = format_delay_response(train_times, train_datetime, from_station, to_station)
    await bot.send_message(chat_id, response_txt, parse_mode='markdown')
