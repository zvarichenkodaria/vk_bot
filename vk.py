import os, vk_api, time, re, sys
from datetime import datetime

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '209129877'
CHAT_1 = 2000000004
CHAT_2 = 2000000004
TAG = "#новости_RevolutionDance"
DB_FILE = "post_ids.txt"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send(session, cid, text, att=None):
    try:
        session.method('messages.send', {
            'peer_id': int(cid), 
            'message': text, 
            'attachment': att, 
            'random_id': 0
        })
    except Exception as e:
        log(f"Ошибка отправки: {e}")

def make_digest(session):
    log("📡 Формирую свежий дайджест...")
    if not os.path.exists(DB_FILE):
        log("ℹ️ Файл с ID пуст.")
        return

    with open(DB_FILE, "r") as f:
        post_ids = [line.strip() for line in f.readlines() if line.strip()]

    if not post_ids:
        log("ℹ️ Нет постов для дайджеста.")
        return

    try:
        # Получаем актуальные тексты постов
        posts = session.method('wall.getById', {'posts': ",".join(post_ids)})
        
        items = []
        for p in posts:
            text = p.get('text', '')
            if TAG in text:
                clean = text.replace(TAG, "").strip()
                # Берем первые два предложения
                sentences = re.split(r'(?<=[.!?])\s+', clean)
                short = " ".join(sentences[:2])
                if short:
                    items.append(f"🔹 {short} [ wall{p['owner_id']}_{p['id']} | Подробнее ]")

        if items:
            msg = "ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:\n\n" + "\n\n".join(items)
            send(session, CHAT_2, msg)
            log("✅ Дайджест отправлен!")
            open(DB_FILE, "w").close() # Очистка после успеха
        else:
            log("ℹ️ Подходящих постов не найдено.")
    except Exception as e:
        log(f"❌ Ошибка при сборке: {e}")

def start():
    log("🚀 БОТ ЗАПУЩЕН (РЕЖИМ ID)")
    last_day = -1
    
    while True:
        try:
            session = vk_api.VkApi(token=TOKEN)
            from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
            lp = VkBotLongPoll(session, GROUP_ID)
            log("✅ Подключение к VK успешно.")

            while True:
                now = datetime.now()
                
                # ТАЙМЕР (6:05 по серверному времени)
                if now.hour == 6 and now.minute == 15 and last_day != now.day:
                    make_digest(session)
                    last_day = now.day

                # Ожидание событий (LongPoll)
                events = lp.check()
                for event in events:
                    if event.type == VkBotEventType.WALL_POST_NEW:
                        p = event.obj.get('wallpost') or event.obj
                        post_id = f"{p['owner_id']}_{p['id']}"
                        
                        # 1. Мгновенный репост
                        send(session, CHAT_1, "📢 Новый пост в группе!", f"wall{post_id}")
                        log(f"✅ Репост выполнен: {post_id}")
                        
                        # 2. Сохранение для дайджеста, если есть тег
                        if TAG in p.get('text', ''):
                            with open(DB_FILE, "a") as f:
                                f.write(f"{post_id}\n")
                            log(f"💾 ID {post_id} сохранен для дайджеста.")

                time.sleep(3)
        except Exception as e:
            log(f"🔄 Рестарт: {e}")
            time.sleep(10)

if __name__ == "__main__":
    start()
