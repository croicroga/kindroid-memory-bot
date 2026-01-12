import logging
import os
import re
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

MEMORY_URL = os.getenv("MEMORY_URL", "https://initial-ai-diary-backend-production.up.railway.app")
KIN_AI_ID = os.getenv("KIN_AI_ID", "kin-001")
KINDROID_API_KEY = os.getenv("KINDROID_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_memories(ai_id, user_id):
    try:
        r = requests.get(f"{MEMORY_URL}/memory/{ai_id}/{user_id}")
        return r.json()["memories"][:3]
    except Exception as e:
        logger.error(f"Memory read error: {e}")
        return []

async def save_memory(ai_id, user_id, content, importance):
    data = {
        "ai_id": ai_id,
        "user_id": user_id,
        "content": content,
        "importance": importance
    }
    try:
        r = requests.post(f"{MEMORY_URL}/memory", json=data)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Memory save error: {e}")
        return False

async def kindroid_chat(prompt, context_memories):
    headers = {
        "Authorization": f"Bearer {KINDROID_API_KEY}",
        "Content-Type": "application/json"
    }

    memories_text = "\n".join([m["content"] for m in context_memories])

    full_prompt = f"""Previously saved memories:
{memories_text}

User: {prompt}

Answer BRIEFLY. To save memory, add at the END:
SAVE_MEMORY: {{ "content": "text to save", "importance": 3 }}"""

    data = {
        "ai_id": KIN_AI_ID,  # L7p9nKcnqDpTwAQiBZSP
        "message": full_prompt
    }

    try:
        r = requests.post("https://api.kindroid.ai/v1/send_message",
                         headers=headers, json=data)
        logger.info(f"Kindroid status: {r.status_code}")
        logger.info(f"Kindroid response: {r.text[:100]}")
        return r.text.strip()  # ← ПРОСТО ТЕКСТ!
    except Exception as e:
        logger.error(f"Kindroid error: {e}")
        return "Ошибка связи с ИИ."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I'm ready.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prompt = update.message.text

    # 1. Читаем память
    memories = await get_memories(KIN_AI_ID, user_id)

    # 2. Спрашиваем Kindroid
    response = await kindroid_chat(prompt, memories)

    # 3. Парсим SAVE_MEMORY
    save_match = re.search(r'SAVE_MEMORY:\s*(\{.*?\})', response, re.DOTALL)

    if save_match:
        memory_data = json.loads(save_match.group(1))
        await save_memory(KIN_AI_ID, user_id, memory_data["content"], memory_data.get("importance", 3))
        # Убираем маркер из ответа
        response = re.sub(r'SAVE_MEMORY:.*?(?=\n|$)', '', response, flags=re.DOTALL).strip()

    await update.message.reply_text(response)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
