from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
import redis, json
from importlib import resources as impresources
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import CommandStart
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware

from aiogram.utils.exceptions import MessageNotModified

# print python path 
import sys, os

# Appent parent dir to python path that can import messages.py as module
real_path = os.path.realpath(__file__)
dir_path = os.path.dirname(real_path)
sys.path.append(os.path.join(dir_path, '..'))
#  print(sys.path)

from birthday_bot.messages import get_rules, get_greeting_message, get_address_msg
from birthday_bot import resources
from birthday_bot.outbox import send_message_to_user

# If ENV is not set, use dotenv
if not os.environ.get('ENV'):
    from dotenv import load_dotenv
    load_dotenv()

# Initialize bot with token from BotFather
env_type = os.environ.get('ENV')
assert (env_type == 'prod' or env_type == 'test'), 'ENV is not set. Expected "prod" or "test". Exiting...'

bot_token = os.environ['BOT_TOKEN']
redis_host = os.environ['REDIS_HOST']
redis_port = os.environ['REDIS_PORT']

bot = Bot(token=bot_token)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Connect to Redis
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)


SAVED_IDS = "attendees_ids"
SAVED_USERS = "attendees_users"
ADMIN_USERS = os.getenv('ADMIN_USERS').split(',')



class AdminFilter(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if str(message.from_user.id) not in ADMIN_USERS:
            await message.answer("You are not authorized to use this command.")
            raise CancelHandler()



# Def function to work with redis

def save_dict_to_redis(key, dict, redis_client):
    redis_client.set(key, json.dumps(dict))

def get_dict_from_redis(key, redis_client):
    dict = redis_client.get(key)
    if dict:
        return json.loads(dict)
    else:
        return {}

def save_attendee(user_id, username, redis_client):
    '''Save attendee to redis dict {user_id: username}'''
    attendees = get_dict_from_redis(SAVED_USERS, redis_client)
    attendees[user_id] = username
    save_dict_to_redis(SAVED_USERS, attendees, redis_client)

def remove_attendee(user_id, redis_client):
    '''Remove attendee from redis dict {user_id: username}'''
    attendees = get_dict_from_redis(SAVED_USERS, redis_client)
    if user_id in attendees:
        del attendees[user_id]
        save_dict_to_redis(SAVED_USERS, attendees, redis_client)

# Inline keyboard buttons
def get_keyboard(user_id):
    is_attending = redis_client.sismember(SAVED_IDS, user_id)
    attend_button_text = 'НЕ ПРИДУ!' if is_attending else 'ПРИДУ!'
    keyboard = InlineKeyboardMarkup().row(
        InlineKeyboardButton(attend_button_text, callback_data='toggle_attend'),
        InlineKeyboardButton('Где и когда!?', callback_data='get_address'),
        InlineKeyboardButton('Кто придет?', callback_data='get_guests'),
        InlineKeyboardButton('Правила', callback_data='rules'),
    )
    return keyboard

# Command handler to start the bot
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    welcome_text = f"Привет, {message.from_user.first_name}!\n"
    welcome_text = f"{welcome_text}\n{get_greeting_message()}"
    await message.reply(welcome_text,
                        reply_markup=get_keyboard(message.from_user.id),
                        parse_mode='Markdown')


@dp.message_handler(commands=['broadcast'], commands_prefix='/')
async def notify_users(message: types.Message):
    broadcast_text = message.get_args()
    if not broadcast_text:
        await message.answer("Please provide a message to broadcast.")
        return False
    
    attendees = get_dict_from_redis(SAVED_USERS, redis_client)
    for user_id, username in attendees.items():
        await send_message_to_user(user_id, broadcast_text, bot, disable_notification = False)


@dp.message_handler(commands=['rules'])
async def send_rules(message: types.Message):
    await message.reply(get_rules(), parse_mode='Markdown')

# Callback query handler to process button presses
@dp.callback_query_handler(lambda c: c.data in ['toggle_attend',
                                                'get_address',
                                                'get_guests',
                                                'rules'])
async def process_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    username = callback_query.from_user.username
    if callback_query.data == 'toggle_attend':
        if redis_client.sismember(SAVED_IDS, user_id):
            redis_client.srem(SAVED_IDS, user_id)
            remove_attendee(user_id, redis_client)
            await bot.answer_callback_query(callback_query.id, "You've been removed from the guest list.")
            # Send message additionally
            await bot.send_message(callback_query.from_user.id, "Вы внесены в список отказавшихся! Но пока карандашом.\nЭто будет иметь последствия!")
        else:
            redis_client.sadd(SAVED_IDS, user_id)
            save_attendee(user_id, username, redis_client)
            await bot.answer_callback_query(callback_query.id, "You've been added to the guest list.")
            await bot.send_message(callback_query.from_user.id, "Вы внесены в список гостей!")
    elif callback_query.data == 'get_address':
        address = get_address_msg()  # Replace with your actual address
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id,
                               address,
                               parse_mode='Markdown',
                               reply_markup=get_keyboard(callback_query.from_user.id),)
        # Send video "resources/home.mp4" additionally
        with impresources.path(resources, 'home.mp4') as path:
            with open(path, 'rb') as video_file:
                await bot.send_video(callback_query.from_user.id,
                                     video=InputFile(video_file),
                                     caption='Видео как добраться!')
        await bot.answer_callback_query(callback_query.id)
        
    elif callback_query.data == 'get_guests':
        # attendees = redis_client.smembers(SAVED_IDS)
        attendees = get_dict_from_redis(SAVED_USERS, redis_client)
        await bot.answer_callback_query(callback_query.id)
        if len(attendees) > 0:
            # users_names = [  for user in list(attendees.values())]
            users_names = '\n'.join([f"@{str(attendee)}" for attendee in list(attendees.values())])
            message_text = f"На данный момент сказали что придут:\n{users_names}\nВсего: {len(attendees)} гостей"
        else:
            message_text = "There are no guests yet. The party is still young!"
        await bot.send_message(callback_query.from_user.id, message_text,
                               reply_markup=get_keyboard(callback_query.from_user.id),
        )
    elif callback_query.data == 'rules':
        message_text = get_rules()
        await bot.send_message(callback_query.from_user.id, message_text, reply_markup=get_keyboard(user_id), parse_mode='Markdown')
        await bot.answer_callback_query(callback_query.id)
    # Refresh the keyboard to update the 'Count me in/out' button text
    try:
        await bot.edit_message_reply_markup(callback_query.from_user.id, callback_query.message.message_id, reply_markup=get_keyboard(user_id))
    except MessageNotModified:
        pass
    
# Run the bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)