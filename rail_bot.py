import json
import logging
from datetime import date
from datetime import datetime

import dateutil
import humanize
from dateutil.parser import parse
from telegram import Update, InlineKeyboardMarkup, \
    InlineKeyboardButton, Bot
from telegram.ext import CallbackQueryHandler, ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler

from train_facade import get_train_times, get_delay_from_api
from train_stations import TRAIN_STATIONS

SELECTED_ID = 'si'
NEXT_STATE = 'ns'

SELECT_ARRIVAL_STATION = 'c_1'
SELECT_DEPARTURE_TIME = 'c_2'
CHECK_DELAYS_FOR_SPECIFIC_TIME = 'c_3'

bot = None


def next_state_is(state):
    def is_state(data):
        d = json.loads(data)
        return d['ns'] == state

    return is_state


def start_bot(token):
    global bot
    bot = Bot(token)
    application = ApplicationBuilder().token(token).build()
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


def get_station_buttons(stations, next_state):
    stations = sorted(stations, key=lambda station: station['english'])
    return [[InlineKeyboardButton(station['english'], callback_data=json.dumps({
        NEXT_STATE: next_state,
        SELECTED_ID: station['id']
    }))]
            for station in stations]


async def select_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_arrival_station command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    callback_data = json.loads(update.callback_query.data)
    departure_station_id = callback_data['si']
    context.chat_data['departure_station_id'] = departure_station_id

    # Get the user's selected departure stations
    buttons = get_station_buttons(list(filter(lambda station: station['id'] != departure_station_id, TRAIN_STATIONS)),
                                  SELECT_DEPARTURE_TIME)

    reply_markup = InlineKeyboardMarkup(buttons)
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, TRAIN_STATIONS))['english']

    await update.callback_query.message.edit_text(
        "Departing from *{departure_station}*. Please select arrival station:".format(
            departure_station=departure_station_name), reply_markup=reply_markup, parse_mode='markdown')

    return "stations_selected"


def format_time_from_str(t, show_day=True):
    request_time = dateutil.parser.isoparse(t)

    return format_time(request_time, show_day)


def format_time(request_time, show_day=True):
    natural_date = humanize.naturalday(request_time)
    absolute_time = datetime.strftime(request_time, '%H:%M')
    if show_day:
        return "{date} at {time}".format(date=natural_date, time=absolute_time)
    else:
        return absolute_time


async def select_departure_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Got select_arrival_station command from user=%s, context=%s, chat_id=%s", update.effective_user,
                 context.chat_data, update.effective_chat.id)

    query = update.callback_query
    callback_data = json.loads(update.callback_query.data)
    selected_station_id = callback_data['si']
    context.chat_data['arrival_station_id'] = selected_station_id
    departure_station_id = context.chat_data['departure_station_id']

    times = get_train_times(context.chat_data['departure_station_id'],
                            context.chat_data['arrival_station_id'])

    buttons = [
        [InlineKeyboardButton(
            "{dep} (arrive {arr})".format(dep=format_time_from_str(dep), arr=format_time_from_str(arr, show_day=False)).capitalize(),
            callback_data=json.dumps({'ns': CHECK_DELAYS_FOR_SPECIFIC_TIME, 'time': dep}))]
        for dep, arr in times]

    reply_markup = InlineKeyboardMarkup(buttons)
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, TRAIN_STATIONS))['english']
    arrival_station_name = next(filter(lambda s: s['id'] == selected_station_id, TRAIN_STATIONS))['english']

    await query.message.edit_text(
        "Departing from *{departure_station}* to *{arrival_station}*. Please select departure time:".format(
            departure_station=departure_station_name, arrival_station=arrival_station_name), reply_markup=reply_markup,
        parse_mode='markdown')

    return "departure_time_selected"


async def check_delays_for_specific_time(update: Update, context: ContextTypes.DEFAULT_TYPE, to_user=None):
    logging.info("Got departure_time_selected command from user=%s, context=%s", update.effective_user,
                 context.chat_data)

    query = update.callback_query
    callback_data = json.loads(query.data)
    selected_time = callback_data['time']
    departure_station_id = context.chat_data['departure_station_id']
    arrival_station_id = context.chat_data['arrival_station_id']

    logging.info("Checking delay from %s to %s on %s", departure_station_id, arrival_station_id, selected_time)

    train_times = get_delay_from_api(departure_station_id,
                                     arrival_station_id, selected_time)

    response_txt = format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id)

    if to_user is None:
        await query.message.edit_text(response_txt, parse_mode='markdown')
    else:
        pass

    return ConversationHandler.END


def format_delay_response(train_times, selected_time, departure_station_id, arrival_station_id):
    departure_station_name = next(filter(lambda s: s['id'] == departure_station_id, TRAIN_STATIONS))['english']
    arrival_station_name = next(filter(lambda s: s['id'] == arrival_station_id, TRAIN_STATIONS))['english']
    last_update_str = '(updated {})'.format(datetime.strftime(datetime.now(), '%H:%M'))
    if train_times.delay_in_minutes > 0:
        # delay_str = "is ⏱️ {delay} minutes late".format(delay=str(train_times))
        departure_str = '️⏱️ {}'.format(format_time(train_times.get_updated_departure()))
        arrival_str = '~{}~ ⏱️ {}'.format(format_time_from_str(train_times.original_arrival, False),
                                          format_time(train_times.get_updated_departure(), False))
    else:
        departure_str = '✅ {}'.format(format_time(train_times.get_updated_departure()))
        arrival_str = format_time_from_str(train_times.original_arrival)
    resposne_txt = "Train from *{departure_station}* to *{arrival_station}*. \n" \
                   "*Departing* *{departure_str}* \n" \
                   "*Arriving* *{arrival_str}* {last_update}.".format(
        departure_station=departure_station_name, arrival_station=arrival_station_name,
        departure_str=departure_str, arrival_str=arrival_str, last_update=last_update_str)
    return resposne_txt


async def send_status_notification(chat_id, from_station, to_station, train_hour: str):
    hour, minute = map(int, train_hour.split(':'))
    train_datetime = datetime.now().replace(hour=hour, minute=minute).isoformat()
    train_times = get_delay_from_api(from_station, to_station, train_hour)
    response_txt = format_delay_response(train_times, train_datetime, from_station, to_station)
    await bot.send_message(chat_id, response_txt, parse_mode='markdown')
