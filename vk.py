import os, vk_api, time, re, sys, json, threading
from datetime import datetime

from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN") 
GROUP_ID = '207903951'

# ID чатов
CHAT_WALL_NOTIFY = 2000000001
CHAT_WEEKLY_DIGEST = 2000000001
CHAT_ADMIN_REPORTS = 2000000005
CHAT_INFORMATORS = 2000000010
CHAT_LOG_MONTHLY = 2000000002  # Чат для логов в конце месяца или при сбросе

TAG = "#новости_RevolutionDance"
DB_FILE = "digest_content.txt"
STATS_FILE = "stats_db.json"  # Файл для хранения баллов

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

# Инициализация базы данных статистики
def init_stats():
    if not os.path.exists(STATS_FILE) or os.path.getsize(STATS_FILE) == 0:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({"informers": {}, "journalists": {}}, f, ensure_ascii=False, indent=4)

def load_stats():
    init_stats()
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=4)

def update_score(role, user_id, delta):
    stats = load_stats()
    uid_str = str(user_id)
    
    if uid_str not in stats[role]:
        stats[role][uid_str] = 0
        
    stats[role][uid_str] += delta
    
    if stats[role][uid_str] < 0:
        stats[role][uid_str] = 0
        
    save_stats(stats)
    return stats[role][uid_str]

def clear_role_stats(role):
    stats = load_stats()
    stats[role] = {}
    save_stats(stats)
    log(f"🗑️ Список [{role}] успешно очищен.")

def get_user_name(vk, user_id):
    try:
        res = vk.users.get(user_ids=user_id)
        if res:
            return f"{res[0]['first_name']} {res[0]['last_name']}"
    except Exception as e:
        log(f"Ошибка получения имени для {user_id}: {e}")
    return f"id{user_id}"

def build_list_text(vk, role_key, title_role):
    stats = load_stats()
    role_data = stats.get(role_key, {})
    
    # Сортируем по убыванию баллов
    sorted_users = sorted(role_data.items(), key=lambda x: x[1], reverse=True)
    
    # Получаем текущий месяц и год на русском
    months = ["январь", "февраль", "март", "апрель", "май", "июнь", 
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
    now = datetime.now()
    month_name = months[now.month - 1]
    
    text = f"Новости {title_role} ({month_name} {now.year})\n"
    
    if not sorted_users:
        text += "Список пока пуст."
        return text
        
    for idx, (uid, score) in enumerate(sorted_users, 1):
        name = get_user_name(vk, int(uid))
        # Ссылки через [id...|...] кликабельны, но НЕ присылают push-уведомлений пользователям
        text += f"{idx}. [id{uid}|{name}] - {score}\n"
        
    return text.strip()

def extract_user_id(text):
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        return int(match.group(1))
    digits = re.findall(r'\d+', text)
    if digits:
        return int(digits[0])
    return None

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
        if not clear_file: 
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

# Процедура принудительного сброса ОДНОЙ конкретной роли
def force_clear_single_role(vk, role):
    try:
        months = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", 
                  "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]
        now = datetime.now()
        month_name = months[now.month - 1]

        if role == "informers":
            list_text = build_list_text(vk, "informers", "информаторов")
            # 1. В беседу информаторов
            send(vk, CHAT_INFORMATORS, f"Внимание! Сделан подсчет новостей:\n{list_text}")
            # 2. В лог-чат
            send(vk, CHAT_LOG_MONTHLY, f"📢 Внеплановые баллы информаторов за {month_name}\n{list_text}")
            # Очищаем только их
            clear_role_stats("informers")
            
        elif role == "journalists":
            list_text = build_list_text(vk, "journalists", "журналистов")
            # 1. В беседу журналистов
            send(vk, CHAT_ADMIN_REPORTS, f"Внимание! Сделан подсчет новостей:\n{list_text}")
            # 2. В лог-чат
            send(vk, CHAT_LOG_MONTHLY, f"📢 Внеплановые баллы журналистов за {month_name}\n{list_text}")
            # Очищаем только их
            clear_role_stats("journalists")

        log(f"✅ Досрочный раздельный сброс для [{role}] успешно выполнен.")
    except Exception as e:
        log(f"Ошибка при досрочном сбросе роли {role}: {e}")

# Плановая процедура полного отчета (1-е число месяца)
def make_monthly_report(vk):
    try:
        log("📊 Начало формирования планового ежемесячного отчета...")
        list_inf = build_list_text(vk, "informers", "информаторов")
        list_jur = build_list_text(vk, "journalists", "журналистов")
        
        # 1. Отправка информаторам
        send(vk, CHAT_INFORMATORS, f"Внимание! Сделан подсчет новостей:\n{list_inf}")
        
        # 2. Отправка журналистам
        send(vk, CHAT_ADMIN_REPORTS, f"Внимание! Сделан подсчет новостей:\n{list_jur}")
        
        # 3. Отправка в лог-чат
        months = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", 
                  "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]
        now = datetime.now()
        month_name = months[now.month - 1]
        
        msg_log = f"📢 Баллы информаторов за {month_name}\n{list_inf}\n\n📢 Баллы журналистов за {month_name}\n{list_jur}"
        send(vk, CHAT_LOG_MONTHLY, msg_log)
        
        # Полное обнуление всей базы
        clear_role_stats("informers")
        clear_role_stats("journalists")
        log("✅ Плановый ежемесячный отчет успешно разослан, статистика обнулена.")
    except Exception as e:
        log(f"Ошибка при создании планового отчета: {e}")

# Фоновая функция для проверки времени
def watchdog(vk):
    last_digest_day = -1
    last_monthly_report_month = -1
    log("⏰ Воркер проверки времени запущен")
    while True:
        try:
            now = datetime.now()
            
            TARGET_HOUR = 4
            TARGET_MINUTE = 0

            # --- 1. Еженедельный дайджест (Понедельник) ---
            if (now.weekday() == 0 and 
                now.hour == TARGET_HOUR and 
                now.minute >= TARGET_MINUTE and 
                last_digest_day != now.day):
                
                log(f"📅 Время пришло ({now.hour}:{now.minute}). Отправляю еженедельный дайджест...")
                make_digest(vk, CHAT_WEEKLY_DIGEST, clear_file=True)
                last_digest_day = now.day
            
            # --- 2. Ежемесячный отчет (1 число месяца) ---
            if (now.day == 1 and 
                now.hour == TARGET_HOUR and 
                now.minute >= TARGET_MINUTE and 
                last_monthly_report_month != now.month):
                
                log(f"📅 Первое число месяца! Время ({now.hour}:{now.minute}). Запускаю расчет баллов...")
                make_monthly_report(vk)
                last_monthly_report_month = now.month

            time.sleep(30) 
        except Exception as e:
            log(f"Ошибка в watchdog: {e}")
            time.sleep(10)

def start():
    log("🚀 ПОПЫТКА ЗАПУСКА...")
    init_stats()
    
    if not TOKEN:
        log("❌ ОШИБКА: Токен не найден!")
        return

    while True:
        try:
            vk_session = vk_api.VkApi(token=TOKEN)
            vk = vk_session.get_api()
            lp = VkBotLongPoll(vk_session, GROUP_ID)
            log("✅ БОТ УСПЕШНО ПОДКЛЮЧЕН")

            timer_thread = threading.Thread(target=watchdog, args=(vk,), daemon=True)
            timer_thread.start()

            for event in lp.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    msg = event.obj.message
                    raw_text = msg.get('text', '')
                    text = raw_text.lower().strip()
                    peer_id = msg.get('peer_id')
                    user_id = msg.get('from_id')
                    cmid = msg.get('conversation_message_id')

                    if text == '/id':
                        send(vk, peer_id, f"ID чата: {peer_id}")

                    elif text == '/test':
                        make_digest(vk, CHAT_ADMIN_REPORTS, clear_file=False)

                    # --- Команды изменения баллов вручную ---
                    elif text.startswith('/plus1') or text.startswith('/minus1'):
                        is_plus = text.startswith('/plus1')
                        delta = 1 if is_plus else -1
                        command_len = 6 if is_plus else 7
                        
                        role = "journalists" if int(peer_id) == CHAT_ADMIN_REPORTS else "informers"
                        role_title = "журналисту" if role == "journalists" else "информатору"
                        
                        target_id = extract_user_id(raw_text[command_len:])
                        if not target_id:
                            target_id = user_id
                        
                        new_score = update_score(role, target_id, delta)
                        t_name = get_user_name(vk, target_id)
                        
                        action_text = "начислен +1 балл" if is_plus else "вычтен 1 балл"
                        send(vk, peer_id, f"⭐ Пользователю [id{target_id}|{t_name}] ({role_title}) {action_text}. Всего баллов: {new_score}")

                    # --- Просмотр списков ---
                    elif text == '/list':
                        list_msg = build_list_text(vk, "informers", "информаторов")
                        send(vk, peer_id, list_msg)

                    elif text == '/listj':
                        list_msg = build_list_text(vk, "journalists", "журналистов")
                        send(vk, peer_id, list_msg)

                    # --- Раздельный досрочный сброс листов ---
                    elif text == '/list_stop':
                        send(vk, peer_id, "⚠️ Вызван досрочный сброс списка ИНФОРМАТОРОВ. Формирую отчеты...")
                        force_clear_single_role(vk, "informers")

                    elif text == '/listj_stop':
                        send(vk, peer_id, "⚠️ Вызван досрочный сброс списка ЖУРНАЛИСТОВ. Формирую отчеты...")
                        force_clear_single_role(vk, "journalists")

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
                        
                        inf_score = update_score("informers", target_user, 1)
                        jur_score = update_score("journalists", admin_id, 1)
                        
                        log(f" Начислены баллы: Информатор {target_user} ({inf_score}), Journalist {admin_id} ({jur_score})")
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
