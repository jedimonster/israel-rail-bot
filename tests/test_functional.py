import os
import unittest

from notification_scheduler import send_notification_for_specific_train_user
from rail_bot import start_sender_bot, bot

# These are functional tests; the following environment variables must be defined:
# * DEV_CHAT_ID - a chat id (channel or user) used to send messages
# * TELEGRAM_TOKEN - a telegram bot token
# * RAIL_TOKEN - rail API token

dev_chat_id = os.environ['DEV_CHAT_ID']


class ScheduledNotificationsTestCase(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        start_sender_bot(os.environ['TELEGRAM_TOKEN'])
        # bot.send_message(dev_chat_id, "Start functional tests")

    async def test_real_train(self):
        await send_notification_for_specific_train_user(chat_id=dev_chat_id, from_station='4600', to_station='7300',
                                                        train_day=1, train_time='16:15')

    async def test_non_existent_train(self):
        await send_notification_for_specific_train_user(chat_id=dev_chat_id, from_station='4600', to_station='7300',
                                                        train_day=1, train_time='16:17')


if __name__ == '__main__':
    unittest.main()
