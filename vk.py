import os
import vk_api
import time
import re
import threading
import schedule
from datetime import datetime, timedelta
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '207903951'

# ID чатов (можно поставить одинаковые или разные для тестов)
CHAT_PEER_ID = 2000000001         # Для мгновенных репостов
CHAT_PEER_ID_DIGEST = 2000000002  # Для еженедельного дайджеста

NEWS_TAG = "#новости_RevolutionDance"
SUBSCRIBE_LINK = f"https://vk.com/club{GROUP_ID}"

# --- ЛОГИКА ДАЙДЖЕСТА ---

def get_digest_text(vk):
    """Собирает новости за 7 дней и формирует список"""
    try:
        # Получаем последние 50 постов
        response = vk.wall.get(owner_id=f"-{GROUP_ID}", count=50)
    except Exception as e:
        print(f"❌ Ошибка при обращении к стене: {e}")
        return None

    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    digest_items = []
    emojis = ["🔹", "🔸", "✅", "📍", "✨", "📢", "🔥"]
    
    for post in response['items']:
        post_date = datetime.fromtimestamp(post['date'])
        
        # Условие: пост за неделю И содержит тег
        if post_date > week_ago and NEWS_TAG in post['text']:
            # Очистка текста: убираем тег и лишние пробелы
            text = post['text'].replace(NEWS_TAG, "").strip()
            text = re.sub(r'^\s+', '', text)
            
            # Берем первые 2 предложения
            sentences = re.split(r'(?<=[.!?])\s+', text)
            clean_text = " ".join(sentences[:2]).strip()
            
            if clean_text:
                post_ref = f"wall{post['owner_id']}_{post['id']}"
                emoji = emojis[len(digest_items) % len(emojis)]
                # Формируем строку с гиперссылкой ВК
                digest_items.append(f"{emoji} {clean_text} [ {post_ref} | Подробнее ]")

    if not digest_items:
        return None

    header = "ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:"
    body = "\n\n".join(digest_items)
    footer = f"\n\nПодписаться на [ {SUBSCRIBE_LINK} | СМИ Revolution Dance ]"
    
    return f"{header}\n\n{body}{footer}"

def send_weekly_digest(vk):
    """Функция для планировщика"""
    print(f"⏳ {datetime.now()}: Начинаю сборку дайджеста...")
    text = get_digest_text(vk)
    
    if text:
        try:
            vk.messages.send(
                peer_id=CHAT_PEER_ID_DIGEST,
                message=text,
                random_id=get_random_id()
            )
            print("🚀 Дайджест успешно отправлен!")
        except Exception as e:
            print(f"⚠️ Ошибка отправки дайджеста: {e}")
    else:
        print("ℹ️ Новостей за неделю не найдено, пост не отправлен.")

def run_scheduler():
    """Цикл планировщика в отдельном потоке"""
    while True:
        schedule.run_pending()
        time.sleep(30)

# --- ОСНОВНАЯ ФУНКЦИЯ БОТА ---

def start_bot():
    if not TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN пуст!", flush=True)
        return

    while True:
        try:
            print(f"=== ЗАПУСК: Группа {GROUP_ID} ===", flush=True)
            
            vk_session = vk_api.VkApi(token=TOKEN)
            vk_session.http.timeout = 60
            vk = vk_session.get_api()
            
            # Настройка расписания
            schedule.clear()
            # ТУТ МЕНЯЕМ ВРЕМЯ ДЛЯ ТЕСТОВ (сейчас понедельник 09:00 МСК)
            schedule.every().day.at("12:15").do(send_weekly_digest, vk=vk)
            
            # Запуск фонового потока планировщика (если еще не запущен)
            if not any(t.name == "DigestThread" for t in threading.enumerate()):
                sched_thread = threading.Thread(target=run_scheduler, name="DigestThread", daemon=True)
                sched_thread.start()
                print("⏲️ Планировщик дайджеста запущен в фоне.")

            longpoll = VkBotLongPoll(vk_session, GROUP_ID)
            print("✅ Бот в сети. Слушаю стену и сообщения...", flush=True)

            for event in longpoll.listen():
                # 1. Логика мгновенного репоста нового поста
                if event.type == VkBotEventType.WALL_POST_NEW:
                    post = event.obj.get('wallpost') or event.obj
                    post_id = post.get('id')
                    owner_id = post.get('owner_id')

                    if post_id:
                        attachment = f"wall{owner_id}_{post_id}"
                        print(f"🔎 Новый пост! Репост в чат {CHAT_PEER_ID}...", flush=True)
                        
                        try:
                            vk.messages.send(
                                peer_id=CHAT_PEER_ID,
                                message="📢 Новый пост в группе!",
                                attachment=attachment,
                                random_id=get_random_id()
                            )
                        except Exception as send_err:
                            print(f"⚠️ Ошибка репоста: {send_err}")

                # 2. Просто логируем сообщения (если нужно)
                elif event.type == VkBotEventType.MESSAGE_NEW:
                    print(f"📩 Сообщение в чате {event.obj.message['peer_id']}")

        except Exception as e:
            print(f"❌ КРИТИЧЕСКИЙ СБОЙ: {e}", flush=True)
            print("⏳ Перезапуск через 15 секунд...")
            time.sleep(15)

if __name__ == "__main__":
    start_bot()
