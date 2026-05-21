import os, vk_api, time, re, sys, json, threading
from datetime import datetime

from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN") 
GROUP_ID = '207903951'

# ID чатов (Проверьте их через /id в самих чатах!)
CHAT_WALL_NOTIFY = 2000000001
CHAT_WEEKLY_DIGEST = 2000000001
CHAT_ADMIN_REPORTS = 2000000005
CHAT_INFORMATORS = 2000000010

TAG = "#новости_RevolutionDance"
DB_FILE = "digest_content.txt"

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

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
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        if not clear_file: # Не спамим в админку, если пусто, только по тесту
            send(vk, target_chat, "⚠️ Файл дайджеста пуст.")
        return
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            header = "⚠️ ТЕСТ ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:" if not clear_file else "ГЛАВНЫЕ НОВОСТИ НЕДЕЛИ:"
            full_msg = f"{header}\n\n{content}\n\n[https://vk.com/revolution_sensation|Подписаться на СМИ Revolution Dance]"
            send(vk, target_chat, full_msg)
            
            if clear_file:
                open(DB_FILE, "w", encoding="utf-8").close()
                log("✅ Еженедельный дайджест отправлен и очищен.")
            else:
                log("🔍 Тестовый дайджест отправлен.")
    except Exception as e:
        log(f"Ошибка дайджеста: {e}")

# Фоновая функция для проверки времени
def watchdog(vk):
    last_day = -1
    log("⏰ Воркер проверки времени запущен")
    while True:
        try:
            now = datetime.now()
            
            # Настройки времени (например, 04:30)
            TARGET_HOUR = 4
            TARGET_MINUTE = 0

            # Условие: Понедельник AND час == 4 AND минута >= 30 AND сегодня еще не отправляли
            if (now.weekday() == 0 and 
                now.hour == TARGET_HOUR and 
                now.minute >= TARGET_MINUTE and 
                last_day != now.day):
                
                log(f"📅 Время пришло ({now.hour}:{now.minute}). Отправляю дайджест...")
                make_digest(vk, CHAT_WEEKLY_DIGEST, clear_file=True)
                
                # Фиксируем, что сегодня (в этот день месяца) отправка уже была
                last_day = now.day
            
            time.sleep(30) # Проверяем каждые 30 секунд для точности
        except Exception as e:
            log(f"Ошибка в watchdog: {e}")
            time.sleep(10)

def start():
    log("🚀 ПОПЫТКА ЗАПУСКА...")
    
    if not TOKEN:
        log("❌ ОШИБКА: Токен не найден!")
        return

    while True:
        try:
            vk_session = vk_api.VkApi(token=TOKEN)
            vk = vk_session.get_api()
            lp = VkBotLongPoll(vk_session, GROUP_ID)
            log("✅ БОТ УСПЕШНО ПОДКЛЮЧЕН")

            # Запускаем watchdog в отдельном потоке, передавая объект vk
            # daemon=True значит, что поток умрет при выключении основного кода
            timer_thread = threading.Thread(target=watchdog, args=(vk,), daemon=True)
            timer_thread.start()

            for event in lp.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    msg = event.obj.message
                    text = msg.get('text', '').lower()
                    peer_id = msg.get('peer_id')
                    user_id = msg.get('from_id')
                    cmid = msg.get('conversation_message_id')

                    if text == '/id':
                        send(vk, peer_id, f"ID чата: {peer_id}")

                    elif text == '/test':
                        make_digest(vk, CHAT_ADMIN_REPORTS, clear_file=False)

                    elif text.startswith('/report'):
                        report_text = msg.get('text')[7:].strip()
                        if not report_text: continue
                        
                        user_info = vk.users.get(user_ids=user_id)[0]
                        full_name = f"{user_info['first_name']} {user_info['last_name']}"
                        
                        send(vk, CHAT_ADMIN_REPORTS, "📢 @all НОВЫЙ ПОСТ!", fwd_cmid=cmid, from_peer=peer_id)
                        send(vk, CHAT_ADMIN_REPORTS, 
                             f"Прислали новость, информатор: [id{user_id}|{full_name}]", 
                             kbd=get_report_keyboard(user_id, peer_id))
                        
                        send(vk, peer_id, "✅ Ваша новость отправлена журналистам!")

                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    payload = event.obj.get('payload')
                    target_user = payload.get('uid')
                    target_chat = payload.get('sid')
                    admin_id = event.obj.user_id     
                    
                    u_info = vk.users.get(user_ids=f"{target_user},{admin_id}")
                    inf_full_name = "Информатор"
                    jur_full_name = "Журналист"
                    
                    for u in u_info:
                        if u['id'] == target_user:
                            inf_full_name = f"{u['first_name']} {u['last_name']}"
                        if u['id'] == admin_id:
                            jur_full_name = f"{u['first_name']} {u['last_name']}"

                    if payload.get('type') == "accept":
                        resp = f"✅ [id{target_user}|Информатор], новость взята в работу!"
                        status = "В РАБОТЕ"
                    else:
                        resp = f"❌ [id{target_user}|Информатор], к сожалению, новость отменена!"
                        status = "ОТМЕНЕНО"

                    send(vk, target_chat, resp)
                    
                    try:
                        new_text = f"Статус: {status}\nИнформатор: [id{target_user}|{inf_full_name}]\nЖурналист: [id{admin_id}|{jur_full_name}]"
                        vk.messages.edit(
                            peer_id=event.obj.peer_id,
                            conversation_message_id=event.obj.conversation_message_id,
                            message=new_text
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
            log(f"🔄 Рестарт LongPoll из-за ошибки: {e}")
            time.sleep(10)

if __name__ == "__main__":
    start()
