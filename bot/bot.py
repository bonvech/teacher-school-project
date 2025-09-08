import asyncio
import requests
import json
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


with open('token.txt') as file:
    API_TOKEN = file.readline().rstrip()
    FOLDER_ID = file.readline().rstrip()
    YANDEX_GPT_KEY = file.readline().rstrip()


URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
dp = Dispatcher()


def yandex_gpt(message):
    try:
        headers = {
            'Authorization': f'Api-Key {YANDEX_GPT_KEY}',
            'x-folder-id': FOLDER_ID,
            'Content-Type': 'application/json'
        }
        
        data = {
            'modelUri': f'gpt://{FOLDER_ID}/yandexgpt/latest',
            'completionOptions': {
                'stream': False,
                'temperature': 0.6,
                'maxTokens': 2000
            },
            'messages': [
                {
                    'role': 'system',
                    'text': 'Ты полезный ассистент, который отвечает на вопросы пользователей.'
                },
                {
                    'role': 'user',
                    'text': message
                }
            ]
        }
        
        response = requests.post(URL, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"API вернул статус {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data.get('error', {}):
                    error_msg += f": {error_data['error']['message']}"
            except:
                error_msg += f": {response.text}"
            return {"error": error_msg}
        
        return response.json()
    except Exception as e:
        return {"error": f"Ошибка при запросе к API: {str(e)}"}


async def main():
    bot = Bot(token=API_TOKEN)
    await dp.start_polling(bot)


@dp.message(Command('start'))
async def cmd_start(msg: Message):
    await msg.answer(f'Привет, {msg.from_user.first_name}! Задайте текстовый вопрос, я постараюсь ответить.')


@dp.message()
async def ai_messaging(msg: Message):
    try:
        await msg.bot.send_chat_action(msg.chat.id, 'typing')
        
        if msg.text:
            result = yandex_gpt(msg.text)
            
            if 'error' in result:
                await msg.answer(f'Ошибка при обращении к Yandex GPT: {result["error"]}')
                return
            
            if 'result' not in result:
                await msg.answer('Неожиданный формат ответа от Yandex GPT')
                return
                
            if 'alternatives' not in result['result'] or len(result['result']['alternatives']) == 0:
                await msg.answer('Неожиданный формат ответа от Yandex GPT')
                return
                
            answer = result['result']['alternatives'][0]['message']['text']
            await msg.answer(answer)
        else:
            await msg.answer('Пожалуйста, задайте текстовый вопрос')
    except Exception as e:
        await msg.answer('Что-то пошло не так...')
        print(f"Ошибка: {e}")


##  --------------------------------
if __name__ == '__main__':
    asyncio.run(main())
    