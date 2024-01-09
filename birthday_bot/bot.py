from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
import redis, json
from importlib import resources as impresources


from aiogram.utils.exceptions import MessageNotModified

# print python path 
import sys, os

# Appent parent dir to python path that can import messages.py as module
real_path = os.path.realpath(__file__)
dir_path = os.path.dirname(real_path)
sys.path.append(os.path.join(dir_path, '..'))
#  mprint(sys.path)

from birthday_bot.messages import get_rules, get_greeting_message, get_address_msg
from birthday_bot import resources

# If ENV is not set, use dotenv
if not os.environ.get('ENV'):
    from dotenv import load_dotenv
    load_dotenv()

# Initialize bot with token from BotFather
assert os.environ['ENV'] == 'prod', 'ENV is not set'
bot_token = os.environ['BOT_TOKEN']
redis_host = os.environ['REDIS_HOST']
redis_port = os.environ['REDIS_PORT']

bot = Bot(token=bot_token)
dp = Dispatcher(bot)

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=16380, db=0)


SAVED_IDS = "attendees_ids"
SAVED_USERS = "attendees_users"


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
        InlineKeyboardButton('Адрес!', callback_data='get_address'),
        InlineKeyboardButton('Кто придет?', callback_data='get_guests'),
        InlineKeyboardButton('ПРАВИЛА!', callback_data='rules'),
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
        else:
            redis_client.sadd(SAVED_IDS, user_id)
            save_attendee(user_id, username, redis_client)
            await bot.answer_callback_query(callback_query.id, "You've been added to the guest list.")
    elif callback_query.data == 'get_address':
        address = get_address_msg()  # Replace with your actual address
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, address)
        # Send video "resources/home.mp4" additionally
        with impresources.path(resources, 'home.mp4') as path:
            with open(path, 'rb') as video_file:
                await bot.send_video(callback_query.from_user.id,
                                     video=InputFile(video_file),
                                     caption='Видео как добраться!')
        
        
    elif callback_query.data == 'get_guests':
        # attendees = redis_client.smembers(SAVED_IDS)
        attendees = get_dict_from_redis(SAVED_USERS, redis_client)
        await bot.answer_callback_query(callback_query.id)
        if len(attendees) > 0:
            # users_names = [  for user in list(attendees.values())]
            users_names = '\n'.join([f"@{str(attendee)}" for attendee in list(attendees.values())])
            message_text = f"Current guest list:\n  {users_names}\nTotal: {len(attendees)} guests"
        else:
            message_text = "There are no guests yet. The party is still young!"
        await bot.send_message(callback_query.from_user.id, message_text)
    elif callback_query.data == 'rules':
        message_text = get_rules()
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, message_text, reply_markup=get_keyboard(user_id))
        
    # Refresh the keyboard to update the 'Count me in/out' button text
    try:
        await bot.edit_message_reply_markup(callback_query.from_user.id, callback_query.message.message_id, reply_markup=get_keyboard(user_id))
    except MessageNotModified:
        pass
    
# Run the bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)