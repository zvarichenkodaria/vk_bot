import os, vk_api, time, re, sys
from datetime import datetime

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '207903951'
CHAT_1 = 2000000001
CHAT_2 = 2000000002
TAG = "#новости_RevolutionDance"
DB_FILE = "digest_content.txt"

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
    log("📡 Сборка финального дайджеста...")
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        log("ℹ️ Нечего отправлять.")
        return

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            # 1. Делаем заголовок ЖИРНЫМ (через ссылку на группу)
            header = f"[public{GROUP_ID}|ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:]"
            
            # 2. Собираем всё вместе
            full_msg = f"{header}\n\n{content}\n\n"
            
            # 3. Красивая подпись со ссылкой
            full_msg += "[https://vk.com/revolution_sensation|Подписаться на СМИ Revolution Dance]"
            
            send(session, CHAT_2, full_msg)
            log("✅ Идеальный дайджест отправлен!")
            
            # Очистка
            open(DB_FILE, "w", encoding="utf-8").close()
            
    except Exception as e:
        log(f"❌ Ошибка: {e}")

def start():
    log("🚀 БОТ ЗАПУЩЕН (FINAL BEAUTY VERSION)")
    last_day = -1
    
    while True:
        try:
            session = vk_api.VkApi(token=TOKEN)
            from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
            lp = VkBotLongPoll(session, GROUP_ID)
            log("✅ Подключение успешно.")

            while True:
                now = datetime.now()
                
                # ТАЙМЕР
                if now.hour == 6 and now.minute == 55 and last_day != now.day:
                    make_digest(session)
                    last_day = now.day

                events = lp.check()
                for event in events:
                    if event.type == VkBotEventType.WALL_POST_NEW:
                        p = event.obj.get('wallpost') or event.obj
                        p_text = p.get('text', '')
                        post_id = f"{p['owner_id']}_{p['id']}"
                        
                        send(session, CHAT_1, "📢 Новый пост в группе!", f"wall{post_id}")
                        
                        if TAG in p_text:
                            clean = p_text.replace(TAG, "").strip()
                            sentences = re.split(r'(?<=[.!?])\s+', clean)
                            short = " ".join(sentences[:2]).strip()
                            if not short: short = "Новый пост"
                            
                            full_url = f"https://vk.com/wall{post_id}"
                            # Формируем строку новости
                            entry = f"💢 {short} [{full_url}|Подробнее]\n\n"
                            
                            with open(DB_FILE, "a", encoding="utf-8") as f:
                                f.write(entry)
                            log(f"💾 Сохранено: {post_id}")

                time.sleep(3)
        except Exception as e:
            log(f"🔄 Рестарт: {e}")
            time.sleep(10)

if __name__ == "__main__":
    start()
