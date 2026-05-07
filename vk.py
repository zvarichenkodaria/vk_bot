import os
import vk_api
import time
import re
import sys
from datetime import datetime, timedelta
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '207903951'
CHAT_PEER_ID = 2000000001
CHAT_PEER_ID_DIGEST = 2000000002
NEWS_TAG = "#новости_RevolutionDance"

def log(msg):
    # Принудительный вывод, который хостинг точно увидит
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

def get_digest_text(vk):
    log("🔎 Собираю новости...")
    try:
        response = vk.wall.get(owner_id=f"-{GROUP_ID}", count=40)
        posts = response.get('items', [])
        
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        digest_items = []
        emojis = ["🔹", "🔸", "✅", "📍", "✨", "📢", "🔥"]
        
        for post in posts:
            p_text = post.get('text', '')
            p_date = datetime.fromtimestamp(post.get('date', 0))
            
            if p_date > week_ago and NEWS_TAG in p_text:
                clean_text = p_text.replace(NEWS_TAG, "").strip()
                clean_text = re.sub(r'^\s+', '', clean_text)
                
                sentences = re.split(r'(?<=[.!?])\s+', clean_text)
                final_text = " ".join(sentences[:2]).strip()
                
                if final_text:
                    post_ref = f"wall{post['owner_id']}_{post['id']}"
                    emoji = emojis[len(digest_items) % len(emojis)]
                    digest_items.append(f"{emoji} {final_text} [ {post_ref} | Подробнее ]")

        if not digest_items:
            log("⚠ Новостей с тегом не найдено.")
            return None
        
        header = "ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:\n\n"
        footer = f"\n\nПодписаться на [https://vk.com/club{GROUP_ID}|СМИ Revolution Dance]"
        return header + "\n\n".join(digest_items) + footer
    except Exception as e:
        log(f"❌ Ошибка в get_digest: {e}")
        return None

def start_bot():
    log("--- ПРОВЕРКА ЗАПУСКА ---")
    if not TOKEN:
        log("❌ ОШИБКА: Нет токена в переменных!")
        return

    try:
        vk_session = vk_api.VkApi(token=TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        log("✅ Подключение к VK успешно.")
    except Exception as e:
        log(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
        return

    last_sent_day = -1

    while True:
        try:
            now = datetime.now()
            
            # --- ВРЕМЯ МЕНЯТЬ ТУТ ---
            # Ставь время (Час, Минута)
            t_hour = 12
            t_min = 28

            if now.hour == t_hour and now.minute == t_min and last_sent_day != now.day:
                log(f"⏰ Пора слать дайджест ({t_hour}:{t_min})")
                digest = get_digest_text(vk)
                if digest:
                    vk.messages.send(peer_id=CHAT_PEER_ID_DIGEST, message=digest, random_id=get_random_id())
                    log("🚀 Дайджест отправлен.")
                last_sent_day = now.day

            # --- ПРОВЕРКА НОВЫХ ПОСТОВ ---
            events = longpoll.check()
            for event in events:
                if event.type == VkBotEventType.WALL_POST_NEW:
                    post = event.obj.get('wallpost') or event.obj
                    att = f"wall{post.get('owner_id')}_{post.get('id')}"
                    vk.messages.send(
                        peer_id=CHAT_PEER_ID, 
                        message="📢 Новый пост в группе!", 
                        attachment=att, 
                        random_id=get_random_id()
                    )
                    log(f"✅ Репост выполнен: {att}")

            time.sleep(2) # Защита от перегрузки CPU

        except Exception as e:
            log(f"⚠ Ошибка в цикле: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
