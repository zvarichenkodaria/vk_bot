import os, vk_api, time, re, sys, json
from datetime import datetime
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '207903951'

CHAT_WALL_NOTIFY = 2000000001    # Уведомления о постах
CHAT_WEEKLY_DIGEST = 2000000001  # Куда кидать дайджест в понедельник
CHAT_ADMIN_REPORTS = 2000000005  # Чат админов (куда летят репорты и тест дайджеста)
CHAT_INFORMATORS = 2000000010    # Чат информаторов (откуда летят репорты)

TAG = "#новости_RevolutionDance"
DB_FILE = "digest_content.txt"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def send(vk, peer_id, text, att=None, kbd=None, fwd_cmid=None, from_peer=None):
    try:
        params = {
            'peer_id': int(peer_id),
            'message': text,
            'attachment': att,
            'random_id': get_random_id()
        }
        if kbd:
            params['keyboard'] = json.dumps(kbd, ensure_ascii=False)
        if fwd_cmid and from_peer:
            params['forward'] = json.dumps({
                'peer_id': int(from_peer),
                'conversation_message_ids': [int(fwd_cmid)],
                'is_reply': False
            }, ensure_ascii=False)
        return vk.messages.send(**params)
    except Exception as e:
        log(f"Ошибка отправки: {e}")
        return None

def get_report_keyboard(user_id, source_peer_id):
    return {
        "inline": True,
        "buttons": [[
            {
                "action": {
                    "type": "callback",
                    "label": "✅ Взять в работу",
                    "payload": {"type": "accept", "uid": user_id, "sid": source_peer_id}
                },
                "color": "positive"
            },
            {
                "action": {
                    "type": "callback",
                    "label": "❌ Отмена",
                    "payload": {"type": "decline", "uid": user_id, "sid": source_peer_id}
                },
                "color": "negative"
            }
        ]]
    }

def make_digest(vk, target_chat, clear_file=True):
    """Функция формирования дайджеста"""
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        send(vk, target_chat, "⚠️ Файл дайджеста пуст.")
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            header = "📊 ПРОБНЫЙ ДАЙДЖЕСТ (БЕЗ ОЧИСТКИ):" if not clear_file else "ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:"
            full_msg = f"{header}\n\n{content}\n\n[https://vk.com/revolution_sensation|Подписаться на СМИ Revolution Dance]"
            send(vk, target_chat, full_msg)
            
            if clear_file:
                open(DB_FILE, "w", encoding="utf-8").close()
                log("✅ Еженедельный дайджест отправлен и очищен.")
            else:
                log("🔍 Тестовый дайджест отправлен в админку.")
    except Exception as e:
        log(f"Ошибка дайджеста: {e}")

def start():
    log("🚀 БОТ ЗАПУЩЕН")
    last_day = -1
    
    while True:
        try:
            vk_session = vk_api.VkApi(token=TOKEN)
            vk = vk_session.get_api()
            lp = VkBotLongPoll(vk_session, GROUP_ID)

            for event in lp.listen():
                now = datetime.now()
                
                # Авто-дайджест (Понедельник 04:00)
                if now.weekday() == 0 and now.hour == 4 and now.minute == 0 and last_day != now.day:
                    make_digest(vk, CHAT_WEEKLY_DIGEST, clear_file=True)
                    last_day = now.day

                if event.type == VkBotEventType.MESSAGE_NEW:
                    msg = event.obj.message
                    text = msg.get('text', '').lower()
                    peer_id = msg.get('peer_id')
                    user_id = msg.get('from_id')
                    cmid = msg.get('conversation_message_id')

                    if text == '/id':
                        send(vk, peer_id, f"ID чата: {peer_id}")

                    # Тестовая команда для проверки содержимого дайджеста
                    elif text == '/test_digest':
                        make_digest(vk, CHAT_ADMIN_REPORTS, clear_file=False)

                    elif text.startswith('/report'):
                        if not msg.get('text')[7:].strip(): continue
                        
                        # 1. СООБЩЕНИЕ С ПЕРЕСЫЛОМ (Репост)
                        send(vk, CHAT_ADMIN_REPORTS, 
                             "📢 НОВЫЙ ПОСТ!", 
                             fwd_cmid=cmid, 
                             from_peer=peer_id)
                        
                        # 2. СООБЩЕНИЕ С КНОПКАМИ
                        send(vk, CHAT_ADMIN_REPORTS, 
                             f"👤 Прислали новость, автор: [id{user_id}|профиль]", 
                             kbd=get_report_keyboard(user_id, peer_id))
                        
                        send(vk, peer_id, "✅ Ваша новость отправлена журналистам!")

                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    payload = event.obj.get('payload')
                    target_user = payload.get('uid')
                    target_chat = payload.get('sid')
                    
                    if payload.get('type') == "accept":
                        resp = f"✅ [id{target_user}|Информатор], новость взята в работу!"
                        status = "В РАБОТЕ"
                    else:
                        resp = f"❌ [id{target_user}|Информатор], к сожалению, новость отменена!"
                        status = "ОТМЕНЕНО"

                    send(vk, target_chat, resp)
                    
                    try:
                        vk.messages.edit(
                            peer_id=event.obj.peer_id,
                            conversation_message_id=event.obj.conversation_message_id,
                            message=f"📊 Статус: {status} | Автор: [id{target_user}|профиль]"
                        )
                    except Exception as e:
                        log(f"Ошибка редактирования: {e}")

                elif event.type == VkBotEventType.WALL_POST_NEW:
                    p = event.obj.get('wallpost') or event.obj
                    p_text = p.get('text', '')
                    post_id = f"{p['owner_id']}_{p['id']}"
                    
                    send(vk, CHAT_WALL_NOTIFY, "📢 Новый пост в группе!", f"wall{post_id}")
                    
                    if TAG in p_text:
                        clean = p_text.replace(TAG, "").strip()
                        sentences = re.split(r'(?<=[.!?])\s+', clean)
                        short = " ".join(sentences[:2]).strip() or "Новый пост"
                        entry = f"💢 {short} [https://vk.com/wall{post_id}|Подробнее]\n\n"
                        with open(DB_FILE, "a", encoding="utf-8") as f:
                            f.write(entry)

        except Exception as e:
            log(f"🔄 Рестарт: {e}")
            time.sleep(10)

if __name__ == "__main__":
    start()
