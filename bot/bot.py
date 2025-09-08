import asyncio
import requests
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


with open('token.txt') as file:
    API_TOKEN = file.readline().rstrip()    # Токен бота Telegram
    FOLDER_ID = file.readline().rstrip()    # Идентификатор каталога Yandex Cloud
    YANDEX_GPT_KEY = file.readline().rstrip()  # API-ключ Yandex
URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
dp = Dispatcher()
def yandex_gpt(message):
   
    response = requests.post(
        URL,
        headers = {
            'Authorization': f'Api-Key {YANDEX_GPT_KEY}',
            'x-folder-id': FOLDER_ID
               },
        json={
            'modelUri':
            f'gpt://{FOLDER_ID}/yandexgpt/latest',
            'completionOptions': {
               'stream': False,
               'temperature': 0.6
              },
        'messages': [
        {
        'role': 'system',
        'text': 'Задавай вопрос. Отвечу'
        },
        {
        'role': 'user',
        'text': message
          }
        ]
        }
      )
    return response.json()
async def main():
    bot=Bot(token=API_TOKEN)
    await dp.start_polling(bot)

@dp.message(Command('start'))
async def cmd_start(msg:Message):
    await msg.answer(f'Привет,{msg.from_user.first_name}! '
    f'Задайте текстовый вопрос, я постараюсь ответить. ' )

@dp.message()
async def ai_messaging(msg: Message):
    try:
        
        await msg.bot.send_chat_action(msg.chat.id,'typing')
        
        if msg.text:
            text=yandex_gpt(msg.text)
            answer = text['result']['alternatives'][0]['message']['text']
            await msg.answer(answer)
        else:
            await msg.answer('Задай вопрос')
    except TypeError:
        await msg.answer('Что-то пошло не так...')

if __name__ == '__main__':
    asyncio.run(main()) 










    
