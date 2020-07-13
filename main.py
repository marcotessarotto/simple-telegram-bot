import os

from telegram import Bot
from telegram.ext import messagequeue as mq, Updater, ConversationHandler, CommandHandler, MessageHandler, Filters, \
    CallbackQueryHandler, run_async

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.utils.request import Request


UI_HELP_COMMAND = 'help'


def help_command_handler(update, context):
    """ Show available bot commands"""

    print("help_command_handler")
    print(update)

    update.message.reply_text(
        "ciao! questo è l'help del bot",
        disable_web_page_preview=True,
        parse_mode='HTML',
    )


class MQBot(Bot):
    """A subclass of Bot which delegates send method handling to MQ"""

    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            print("MQBot - __del__")
            self._msg_queue.stop()
        except Exception as error:
            print(f"error in MQBot.__del__ : {error}")
            pass

    @mq.queuedmessage
    def send_message(self, chat_id, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments"""

        e = None
        try:
            return super(MQBot, self).send_message(chat_id, *args, **kwargs)
        except Unauthorized as error:
            # remove chat_id from conversation list
            # orm_user_blocks_bot(chat_id)
            e = error
        except BadRequest as error:
            # handle malformed requests - read more below!
            print("BadRequest")
            e = error
        except TimedOut as error:
            # handle slow connection problems
            print("TimedOut")
            e = error
        except NetworkError as error:
            # handle other connection problems
            print("NetworkError")
            e = error
        except ChatMigrated as error:
            # the chat_id of a group has changed, use e.new_chat_id instead
            print("ChatMigrated")
            e = error
        except TelegramError as error:
            # handle all other telegram related errors
            print("TelegramError")
            e = error


def main():
    print("starting bot...")

    from pathlib import Path
    token_file = Path('token.txt')

    token = os.environ.get('TOKEN') or open(token_file).read().strip()

    print(f"len(token) = {len(token)}")

    # @user2837467823642_bot

    # https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits
    q = mq.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017)  # 5% safety margin in messaging flood limits
    # set connection pool size for bot
    request = Request(con_pool_size=8)
    my_bot = MQBot(token, request=request, mqueue=q)

    global global_bot_instance
    global_bot_instance = my_bot

    updater = Updater(bot=my_bot, use_context=True)
    dp = updater.dispatcher

    job_queue = updater.job_queue

    dp.add_handler(CommandHandler(UI_HELP_COMMAND, help_command_handler))

    # start updater
    updater.start_polling()

    # Stop the bot if you have pressed Ctrl + C or the process has received SIGINT, SIGTERM or SIGABRT
    updater.idle()

    print("terminating bot")

    try:
        request.stop()
        q.stop()
        my_bot.__del__()
    except Exception as e:
        print(e)

    # https://stackoverflow.com/a/40525942/974287
    print("before os._exit")
    os._exit(0)


if __name__ == '__main__':
    main()
