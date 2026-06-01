import os
import vk_api
import time
import re
import sys
import json
import threading
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
PLACE_FILE = "place_db.json"  # Файл для отметок /place

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

# --- ИНИЦИАЛИЗАЦИЯ И РАБОТА С БАЗАМИ ДАННЫХ ---
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

def init_place_db():
    if not os.path.exists(PLACE_FILE) or os.path.getsize(PLACE_FILE) == 0:
        with open(PLACE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)

def load_place_db():
    init_place_db()
    with open(PLACE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_place_db(data):
    with open(PLACE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def build_list_text(vk, role_key, title_role):
    stats = load_stats()
    role_data = stats.get(role_key, {})
    
    sorted_users = sorted(role_data.items(), key=lambda x: x[1], reverse=True)
    
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
        text += f"{idx}. [id{uid}|{name}] - {score}\n"
        
    return text.strip()

def build_individual_score_text(vk, role_key, title_role, user_id):
    stats = load_stats()
    role_data = stats.get(role_key, {})
    uid_str = str(user_id)
    
    months = ["январь", "февраль", "март", "апрель", "май", "июнь", 
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
    now = datetime.now()
    month_name = months[now.month - 1]
    
    name = get_user_name(vk, user_id)
    score = role_data.get(uid_str, 0)
    
    return f"⭐ Статистика {title_role} ({month_name} {now.year}):\n[id{user_id}|{name}] — {score} баллов."

def build_place_list_text(vk):
    data = load_place_db()
    if not data:
        return "📋 Списки отметившихся пока пусты."
        
    months = ["январь", "февраль", "март", "апрель", "май", "июнь", 
              "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
    now = datetime.now()
    month_name = months[now.month - 1]
    
    text = f"📋 Список отметившихся информаторов ({month_name} {now.year}):\n"
    for idx, (uid, info) in enumerate(data.items(), 1):
        custom_id = info.get('custom_id', 'не указан')
        text += f"{idx}. [id{uid}|{info['name']}] ({custom_id}) — {info['fraction'].upper()} ({info['time']})\n"
        
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

# --- ЛОГИКА ОЧИСТКИ И ИСКЛЮЧЕНИЯ (KICK) ---
def kick_unregistered_users(vk):
    try:
        log("🚨 Начинается процедура зачистки не отписавшихся информаторов...")
        
        journalists_ids = set()
        try:
            members = vk.messages.getConversationMembers(peer_id=CHAT_ADMIN_REPORTS)
            for profile in members.get('profiles', []):
                journalists_ids.add(profile['id'])
        except Exception as e:
            log(f"Не удалось получить участников чата журналистов для исключения из ПК: {e}")
            
        registered_data = load_place_db()
        registered_ids = {int(uid) for uid in registered_data.keys()}
        
        try:
            bot_info = vk.groups.getById()
            bot_id = -bot_info[0]['id'] 
            group_raw_id = bot_info[0]['id']
        except:
            bot_id = 0
            group_raw_id = 0

        white_list = journalists_ids.union(registered_ids)
        if bot_id: white_list.add(bot_id)
        if group_raw_id: white_list.add(group_raw_id)
        
        inf_chat_members = vk.messages.getConversationMembers(peer_id=CHAT_INFORMATORS)
        
        kicked_count = 0
        kicked_names = []
        
        for item in inf_chat_members.get('items', []):
            member_id = item.get('member_id')
            
            if member_id > 0 and member_id not in white_list:
                if item.get('is_admin'):
                    continue
                    
                user_name = get_user_name(vk, member_id)
                log(f"⚠️ Исключаю: {user_name} (id{member_id}) — нет отметки в /place")
                
                try:
                    vk.messages.removeChatUser(chat_id=CHAT_INFORMATORS - 2000000000, user_id=member_id)
                    kicked_count += 1
                    kicked_names.append(f"[id{member_id}|{user_name}]")
                    time.sleep(2.0)  
                except Exception as ex:
                    log(f"Не удалось исключить id{member_id}: {ex}")
                    
        report_msg = f"🧹 Автоматическая зачистка завершена!\nИсключено пользователей: {kicked_count}\n"
        if kicked_names:
            report_msg += "Список кикнутых:\n" + "\n".join(f"- {name}" for name in kicked_names)
        else:
            report_msg += "Все информаторы вовремя прошли проверку."
            
        send(vk, CHAT_INFORMATORS, f"⚙️ Ночная проверка завершена. Те, кто не оставил отметку, были исключены из беседы.")
        send(vk, CHAT_LOG_MONTHLY, f"📋 ОТЧЕТ О СЕЗОННОЙ ЧИСТКЕ ЧАТА ИНФОРМАТОРОВ:\n\n{report_msg}")
        log(f"✅ Зачистка окончена. Кикнуто: {kicked_count}")
        
    except Exception as e:
        log(f"Критическая ошибка в блоке зачистки: {e}")

# --- ОСТАЛЬНЫЕ АВТОМАТИЧЕСКИЕ ПРОЦЕДУРЫ ---
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

def force_clear_single_role(vk, role):
    try:
        months = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", 
                  "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]
        now = datetime.now()
        month_name = months[now.month - 1]

        if role == "informers":
            list_text = build_list_text(vk, "informers", "информаторов")
            send(vk, CHAT_INFORMATORS, f"Внимание! Сделан подсчет новостей:\n{list_text}")
            send(vk, CHAT_LOG_MONTHLY, f"📢 Внеплановые баллы информаторов за {month_name}\n{list_text}")
            clear_role_stats("informers")
            
        elif role == "journalists":
            list_text = build_list_text(vk, "journalists", "журналистов")
            send(vk, CHAT_ADMIN_REPORTS, f"Внимание! Сделан подсчет новостей:\n{list_text}")
            send(vk, CHAT_LOG_MONTHLY, f"📢 Внеплановые баллы журналистов за {month_name}\n{list_text}")
            clear_role_stats("journalists")

        log(f"✅ Досрочный раздельный сброс для [{role}] успешно выполнен.")
    except Exception as e:
        log(f"Ошибка при досрочном сбросе роли {role}: {e}")

def make_monthly_report(vk):
    try:
        log("📊 Начало формирования планового ежемесячного отчета...")
        list_inf = build_list_text(vk, "informers", "информаторов")
        list_jur = build_list_text(vk, "journalists", "журналистов")
        
        send(vk, CHAT_INFORMATORS, f"Внимание! Сделан подсчет новостей:\n{list_inf}")
        send(vk, CHAT_ADMIN_REPORTS, f"Внимание! Сделан подсчет новостей:\n{list_jur}")
        
        months = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", 
                  "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]
        now = datetime.now()
        month_name = months[now.month - 1]
        
        msg_log = f"📢 Баллы информаторов за {month_name}\n{list_inf}\n\n📢 Баллы журналистов за {month_name}\n{list_jur}"
        send(vk, CHAT_LOG_MONTHLY, msg_log)
        
        clear_role_stats("informers")
        clear_role_stats("journalists")
        log("✅ Плановый ежемесячный отчет успешно разослан, статистика обнулена.")
    except Exception as e:
        log(f"Ошибка при создании планового отчета: {e}")

# --- ФОНОВЫЙ НАБЛЮДАТЕЛЬ ВРЕМЕНИ (WATCHDOG) ---
def watchdog(vk):
    last_digest_day = -1
    last_monthly_report_month = -1
    last_check_day = -1
    last_kick_day = -1
    log("⏰ Воркер проверки времени запущен")
    
    while True:
        try:
            now = datetime.now()
            TARGET_HOUR = 4
            TARGET_MINUTE = 0

            # --- 1. Еженедельный дайджест (Понедельник) ---
            if (now.weekday() == 0 and 
                now.hour == TARGET_HOUR and 
                now.minute == TARGET_MINUTE and 
                last_digest_day != now.day):
                
                last_digest_day = now.day
                log(f"📅 Время пришло ({now.hour}:{now.minute}). Отправляю еженедельный дайджест...")
                make_digest(vk, CHAT_WEEKLY_DIGEST, clear_file=True)
            
            # --- 2. Ежемесячный отчет по баллам (1 число месяца) ---
            if (now.day == 1 and 
                now.hour == TARGET_HOUR and 
                now.minute == TARGET_MINUTE and 
                last_monthly_report_month != now.month):
                
                last_monthly_report_month = now.month
                log(f"📅 Первое число месяца! Время ({now.hour}:{now.minute}). Запускаю расчет баллов...")
                make_monthly_report(vk)

            # --- 3. Сезонная рассылка проверки информаторов ---
            if (now.day == 1 and now.month in [1, 3, 6, 9] and
                now.hour == TARGET_HOUR and now.minute == TARGET_MINUTE and
                last_check_day != now.day):
                
                last_check_day = now.day
                log("📢 Начало нового сезона! Сбрасываю базу /place и отправляю уведомление...")
                save_place_db({})
                
                alert_text = "🔔 @all Проверка информаторов! Просьба отписаться каждого о своём местонахождении по шаблону:\n\n/place Айди Фракция\nДалее прикрепите скриншот страницы «Мой кот/Моя кошка»\n\nФракцию можно писать как кратко, так и полностью!\nОтписываться можно как в ЛС группы, так и в данную беседу!\nВ случае отсутствия отписи вы будете исключены ночью 3 числа месяца."
                
                send(vk, CHAT_INFORMATORS, alert_text)
                send(vk, CHAT_LOG_MONTHLY, f"📢 Сезонная проверка запущена в чате информаторов!\nТекст: {alert_text}")

            # --- 4. Сезонный автоматический кик не отписавшихся ---
            if (now.day == 3 and now.month in [1, 3, 6, 9] and
                now.hour == TARGET_HOUR and now.minute == TARGET_MINUTE and
                last_kick_day != now.day):
                
                last_kick_day = now.day
                kick_unregistered_users(vk)

            time.sleep(30) 
        except Exception as e:
            log(f"Ошибка в watchdog: {e}")
            time.sleep(10)

# --- ГЛАВНЫЙ СТАРТ И ОБРАБОТЧИК СОБЫТИЙ ---
def start():
    log("🚀 ПОПЫТКА ЗАПУСКА...")
    init_stats()
    init_place_db()
    
    if not TOKEN:
        log("❌ ОШИБКА: Токен не найден!")
        return

    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()

    # Поток watchdog запускается строго ОДИН раз до входа в бесконечный цикл LongPoll
    timer_thread = threading.Thread(target=watchdog, args=(vk,), daemon=True)
    timer_thread.start()

    while True:
        try:
            lp = VkBotLongPoll(vk_session, GROUP_ID)
            log("✅ БОТ УСПЕШНО ПОДКЛЮЧЕН К LONGPOLL")

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

                    # --- Команда Справки для информаторов ---
                    elif text == '/help':
                        help_msg = (
                            "ℹ️ Справка по командам для информаторов:\n\n"
                            "ПРЕДЛОЖКА:\n"
                            "/report [текст и картинки] - предложить новость.\n\n"
                            "СТАТИСТИКА:\n"
                            "/list - посмотреть топ баллов информаторов.\n"
                            "/indlist - узнать свои личные баллы.\n\n"
                            "ПЕРЕПИСЬ О ПРЕБЫВАНИИ:\n"
                            "/place [Айди] [Фракция] [скриншот] - отметиться.\n"
                        )
                        send(vk, peer_id, help_msg)

                    # --- Полная админская справка ---
                    elif text == '/helpj':
                        help_msg = (
                            "⚙️ ПОЛНЫЙ СПИСОК КОМАНД БОТА (Admin/Journalists):\n\n"
                            "ПРОСМОТР СПИСКОВ:\n"
                            "/list - баллы информаторов за месяц.\n"
                            "/listj - баллы журналистов за месяц.\n"
                            "/indlist - личные баллы информаторов.\n"
                            "/indlistj личные баллы журналистов.\n\n"
                            "РУЧНОЕ УПРАВЛЕНИЕ БАЛЛАМИ:\n"
                            "/plus1 - добавить 1 балл себе.\n"
                            "/plus1 [id/упоминание] - добавить 1 балл пользователю.\n"
                            "/minus1 - вычесть 1 балл у себя.\n"
                            "/minus1 [id/упоминание] - вычесть 1 балл у пользователя.\n"
                            "💡 (В чате журналистов баллы идут журналистам, в остальных - информаторам)\n\n"
                            "СБРОС И ОБНУЛЕНИЕ БАЛЛОВ:\n"
                            "/list_stop - досрочно закрыть информаторов.\n"
                            "/listj_stop - досрочно закрыть журналистов.\n\n"
                            "ПЕРЕПИСЬ (/place):\n"
                            "/place [Айди] [Фракция] [скриншот] - запись в базу пребытий.\n"
                            "/check_place - полный список отписавшихся.\n\n"
                            "ТЕСТЫ И СВЯЗЬ:\n"
                            "/id - узнать ID текущей беседы.\n"
                            "/test - выслать тестовый дайджест новостей."
                        )
                        send(vk, peer_id, help_msg)
                        
                    # --- Просмотр списка отметившихся /check_place ---
                    elif text == '/check_place':
                        place_msg = build_place_list_text(vk)
                        send(vk, peer_id, place_msg)

                    # --- Команда сезонной отметки /place ---
                    elif text.startswith('/place'):
                        parts = raw_text.split(maxsplit=2)
                        if len(parts) < 3:
                            send(vk, peer_id, "⚠️ Ошибка! Заполните команду строго по шаблону:\n/place Айди Фракция\n(и скриншот страницы «Мой кот/Моя кошка»)")
                            continue
                        
                        user_custom_id = parts[1].strip()
                        user_fraction = parts[2].strip()
                        user_name = get_user_name(vk, user_id)
                        
                        place_data = load_place_db()
                        place_data[str(user_id)] = {
                            "name": user_name,
                            "custom_id": user_custom_id,
                            "fraction": user_fraction,
                            "time": datetime.now().strftime('%d.%m.%Y %H:%M')
                        }
                        save_place_db(place_data)
                        
                        send(vk, peer_id, f"✅ Отметка принята! [id{user_id}|{user_name}] внесен в список.")
                        
                        log_entry = f"📦 Пользователь [id{user_id}|{user_name}] оставил отметку:\nID: {user_custom_id}\nФракция: {user_fraction}\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                        send(vk, CHAT_LOG_MONTHLY, log_entry)

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

                    # --- Просмотр полных списков ---
                    elif text == '/list':
                        list_msg = build_list_text(vk, "informers", "информаторов")
                        send(vk, peer_id, list_msg)

                    elif text == '/listj':
                        list_msg = build_list_text(vk, "journalists", "журналистов")
                        send(vk, peer_id, list_msg)

                    # --- Просмотр индивидуальной статистики ---
                    elif text == '/indlist':
                        ind_msg = build_individual_score_text(vk, "informers", "информатора", user_id)
                        send(vk, peer_id, ind_msg)

                    elif text == '/indlistj':
                        ind_msg = build_individual_score_text(vk, "journalists", "журналиста", user_id)
                        send(vk, peer_id, ind_msg)

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

                # --- Обработка кликов по инлайн-кнопкам (Callback-события) ---
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

                # --- Парсинг новых постов группы на стене ---
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
