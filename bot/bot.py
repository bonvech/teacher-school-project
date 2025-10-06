import asyncio
import requests
import json
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

with open('token.txt') as file:
    API_TOKEN = file.readline().rstrip()
    FOLDER_ID = file.readline().rstrip()
    YANDEX_GPT_KEY = file.readline().rstrip()

URL = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
dp = Dispatcher()

# Словарь для хранения последних вопросов пользователей
user_last_questions = {}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    
    # Таблица с вопросами
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица с ответами пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            user_answer TEXT NOT NULL,
            ai_feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES questions (id)
        )
    ''')
    
    # Загружаем вопросы из файла
    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        try:
            with open('questions.txt', 'r', encoding='utf-8') as f:
                questions = [line.strip() for line in f if line.strip()]
            
            for question in questions:
                # Разделяем вопрос и категорию (если есть)
                if '|' in question:
                    question_text, category = question.split('|', 1)
                    cursor.execute("INSERT INTO questions (question_text, category) VALUES (?, ?)", 
                                 (question_text.strip(), category.strip()))
                else:
                    cursor.execute("INSERT INTO questions (question_text) VALUES (?)", (question.strip(),))
            
            print(f"Загружено {len(questions)} вопросов из файла")
        except FileNotFoundError:
            print("Файл questions.txt не найден. Вопросы не загружены.")
        except Exception as e:
            print(f"Ошибка при загрузке вопросов: {e}")
    
    conn.commit()
    conn.close()

# Функция для получения случайного вопроса
def get_random_question():
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text FROM questions ORDER BY RANDOM() LIMIT 1")
    question = cursor.fetchone()
    conn.close()
    return question

# Функция для сохранения ответа пользователя
def save_user_answer(user_id, question_id, user_answer, ai_feedback=None):
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_answers (user_id, question_id, user_answer, ai_feedback)
        VALUES (?, ?, ?, ?)
    ''', (user_id, question_id, user_answer, ai_feedback))
    conn.commit()
    conn.close()

# Функция для получения истории ответов пользователя
def get_user_answers(user_id):
    conn = sqlite3.connect('questions.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT q.question_text, ua.user_answer, ua.ai_feedback, ua.created_at
        FROM user_answers ua
        JOIN questions q ON ua.question_id = q.id
        WHERE ua.user_id = ?
        ORDER BY ua.created_at DESC
    ''', (user_id,))
    answers = cursor.fetchall()
    conn.close()
    return answers

def yandex_gpt(message, system_prompt=None):
    try:
        headers = {
            'Authorization': f'Api-Key {YANDEX_GPT_KEY}',
            'x-folder-id': FOLDER_ID,
            'Content-Type': 'application/json'
        }
        
        if system_prompt is None:
            system_prompt = 'Ты полезный ассистент, который отвечает на вопросы пользователей.'
        
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
                    'text': system_prompt
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

# Функция для экспертизы ответа пользователя
def analyze_user_answer(question, user_answer):
    system_prompt = '''Ты - эксперт по анализу ответов пользователей. 
    Проанализируй ответ пользователя на заданный вопрос и дай конструктивную обратную связь.
    Оценивай полноту ответа, конкретику, релевантность. 
    Предложи, как можно улучшить ответ, если это необходимо.'''
    
    prompt = f"""
    Вопрос: {question}
    Ответ пользователя: {user_answer}
    
    Проанализируй данный ответ и дай развернутую экспертизу.
    """
    
    return yandex_gpt(prompt, system_prompt)

async def main():
    # Инициализируем базу данных при запуске
    init_db()
    bot = Bot(token=API_TOKEN)
    await dp.start_polling(bot)

@dp.message(Command('start'))
async def cmd_start(msg: Message):
    welcome_text = f'''Привет, {msg.from_user.first_name}!
    
Я помогу тебе подготовиться к собеседованию или проанализировать твои ответы на вопросы.

Доступные команды:
/question - получить случайный вопрос для практики
/history - посмотреть историю своих ответов и экспертизу
/analyze - проанализировать произвольный текст

Просто отправь мне ответ на вопрос, и я его проанализирую!'''
    await msg.answer(welcome_text)

@dp.message(Command('question'))
async def cmd_question(msg: Message):
    question_data = get_random_question()
    if question_data:
        question_id, question_text = question_data
        # Сохраняем вопрос для этого пользователя
        user_last_questions[msg.from_user.id] = (question_id, question_text)
        await msg.answer(f"Вопрос: {question_text}\n\nОтправь свой ответ, и я его проанализирую!")
    else:
        await msg.answer("В базе данных нет вопросов. Добавьте вопросы в файл questions.txt")

@dp.message(Command('history'))
async def cmd_history(msg: Message):
    answers = get_user_answers(msg.from_user.id)
    if not answers:
        await msg.answer("У вас пока нет сохраненных ответов.")
        return
    
    response = "📊 История ваших ответов:\n\n"
    for i, (question, answer, feedback, date) in enumerate(answers[:5], 1):
        response += f"{i}. ❓ Вопрос: {question}\n"
        response += f"   💬 Ваш ответ: {answer[:100]}...\n"
        if feedback:
            response += f"   📝 Экспертиза: {feedback[:100]}...\n"
        response += f"   📅 {date[:10]}\n\n"
    
    await msg.answer(response)

@dp.message(Command('analyze'))
async def cmd_analyze(msg: Message):
    await msg.answer("Отправь мне текст в формате:\nВопрос: [твой вопрос]\nОтвет: [твой ответ]\n\nИ я его проанализирую!")

@dp.message()
async def handle_user_response(msg: Message):
    try:
        user_text = msg.text.strip()
        
        # Если сообщение начинается с "Вопрос:" и "Ответ:" - это прямой запрос на анализ
        if user_text.startswith("Вопрос:") and "Ответ:" in user_text:
            parts = user_text.split("Ответ:")
            if len(parts) == 2:
                question = parts[0].replace("Вопрос:", "").strip()
                user_answer = parts[1].strip()
                
                await msg.answer("🔍 Анализирую ваш ответ...")
                
                result = analyze_user_answer(question, user_answer)
                
                if 'error' in result:
                    await msg.answer(f'Ошибка при анализе: {result["error"]}')
                    return
                
                if 'result' in result and 'alternatives' in result['result'] and result['result']['alternatives']:
                    analysis = result['result']['alternatives'][0]['message']['text']
                    
                    # Сохраняем в базу (question_id = 0 для произвольных вопросов)
                    save_user_answer(msg.from_user.id, 0, user_answer, analysis)
                    
                    response = f"✅ Анализ вашего ответа:\n\n{analysis}"
                    await msg.answer(response)
                else:
                    await msg.answer("Не удалось получить анализ ответа.")
            
            return

        # Обычный режим - анализируем ответ на последний вопрос
        if msg.from_user.id not in user_last_questions:
            await msg.answer("Сначала получите вопрос с помощью /question")
            return
            
        await msg.bot.send_chat_action(msg.chat.id, 'typing')
        
        # Получаем последний вопрос для этого пользователя
        question_id, question_text = user_last_questions[msg.from_user.id]
        
        result = analyze_user_answer(question_text, user_text)
        
        if 'error' in result:
            await msg.answer(f'Ошибка при анализе: {result["error"]}')
            return
        
        if 'result' in result and 'alternatives' in result['result'] and result['result']['alternatives']:
            analysis = result['result']['alternatives'][0]['message']['text']
            
            # Сохраняем ответ и анализ в базу
            save_user_answer(msg.from_user.id, question_id, user_text, analysis)
            
            response = f"❓ Вопрос: {question_text}\n\n"
            response += f"💬 Ваш ответ: {user_text}\n\n"
            response += f"📝 Экспертиза ИИ:\n{analysis}"
            
            await msg.answer(response)
            
            # Удаляем вопрос из памяти, чтобы следующий ответ не считался ответом на тот же вопрос
            # Или оставляем, если хотим дать возможность переотвечать на тот же вопрос
            # del user_last_questions[msg.from_user.id]
            
        else:
            await msg.answer("Не удалось проанализировать ответ.")
            
    except Exception as e:
        await msg.answer('Произошла ошибка при обработке вашего ответа.')
        print(f"Ошибка: {e}")

if __name__ == '__main__':
    asyncio.run(main())
