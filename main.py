import datetime
import os

import telegram
from telegram import Bot
from telegram.ext import messagequeue as mq, Updater, ConversationHandler, CommandHandler, MessageHandler, Filters, \
    CallbackQueryHandler, run_async

from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError)
from telegram.utils.request import Request


UI_HELP_COMMAND = 'help'

CALLBACK_NAME, CALLBACK_SURNAME, CALLBACK_AGE = range(3)

user_dictionary = {}

def help_command_handler(update, context):
    """ Show available bot commands"""

    print("help_command_handler")
    print(update)

    try:
        first_name = update.message.chat.first_name
    except AttributeError:
        print("eccezione AttributeError")
        first_name = "-"


    print(f"first_name = {first_name}")


    update.message.reply_text(
        f"ciao {first_name}! questo è l'help del bot",
        disable_web_page_preview=True,
        parse_mode='HTML',
    )


def start_command_handler(update, context):
    user_id = update.effective_user.id

    print(f"start_command_handler user_id = {user_id}")

    update.message.reply_text(
        f'ciao {update.message.from_user.first_name}! '
    )


def generic_message_handler(update, context):
    message_text = update.message.text

    print(f"generic_message_handler - message_text = {message_text}")

time_msg = None


def get_time_command_handler(update, context):
    # diamo all'utente l'ora corrente
    global time_msg

    d = datetime.datetime.now()

    if time_msg:
        time_msg.edit_text(
            text=f"***l'ora corrente è {d}"
        )
    else:
        promise = update.message.reply_text(
            text=f"l'ora corrente è {d}"
        )

        time_msg = promise.result()

    print(time_msg)


def info_command_handler(update, context):
    print("info_command_handler")

    user_id = update.effective_user.id

    # voglio controllare se user_id è una chiave di user_dictionary

    if user_id in user_dictionary:
        update.message.reply_text(
            f'ti ho già chiesto le informazioni che sono: { user_dictionary[user_id] }'
        )
        return ConversationHandler.END

    update.message.reply_text(
        f'ok, ora ti chiederò il nome:'
    )

    return CALLBACK_NAME


class TelegramUser:

    def __str__(self):
        return 'TelegramUser: name=' + self.name + ', surname=' + self.surname + ', age=' + self.age


def callback_name(update, context):
    name = update.message.text

    print(f"name = {name}")

    user_id = update.effective_user.id

    u = TelegramUser()

    user_dictionary[user_id] = u
    u.name = name

    update.message.reply_text(
        text='grazie, ora dimmi il tuo cognome:'
    )

    return CALLBACK_SURNAME


def callback_surname(update, context):
    surname = update.message.text

    print(f"surname = {surname}")

    user_id = update.effective_user.id

    u = user_dictionary[user_id]
    u.surname = surname

    update.message.reply_text(
        text='grazie, ora dammi la tua età:'
    )

    return CALLBACK_AGE


def callback_age(update, context):
    age = update.message.text

    print(f"age = {age}")

    user_id = update.effective_user.id

    u = user_dictionary[user_id]
    u.age = age

    print(u)

    update.message.reply_text(
        text='grazie, finito!'
    )

    return ConversationHandler.END


def fallback_conversation_handler(update, context):
    text = update.message.text
    print(f'fallback_conversation_handler {text}')
    return ConversationHandler.END


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

    # *** boilerplate start
    from pathlib import Path
    token_file = Path('token.txt')

    token = os.environ.get('TOKEN') or open(token_file).read().strip()
    # None (simile a null in Java)
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
    # *** boilerplate end

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('info', info_command_handler),
        ],
        states={
            CALLBACK_NAME: [MessageHandler(Filters.text, callback_name)],
            CALLBACK_SURNAME: [MessageHandler(Filters.text, callback_surname)],
            CALLBACK_AGE: [MessageHandler(Filters.text, callback_age)],
        },
        fallbacks=[
            MessageHandler(Filters.all, fallback_conversation_handler)
        ]
    )

    dp.add_handler(conv_handler)

    dp.add_handler(CommandHandler('start', start_command_handler))
    dp.add_handler(CommandHandler('help', help_command_handler))

    dp.add_handler(CommandHandler('ora', get_time_command_handler))

    dp.add_handler(MessageHandler(Filters.text, generic_message_handler))

    # *** boilerplate start
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
    # *** boilerplate end


if __name__ == '__main__':
    main()
