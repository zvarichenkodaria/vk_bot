import os
import subprocess
import sys

# 1. СИЛОВАЯ УСТАНОВКА БИБЛИОТЕКИ (если хостинг тупит)
try:
    import vk_api
except ImportError:
    print("Библиотека vk_api не найдена. Пытаюсь установить...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "vk_api"])
    import vk_api

from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# 2. НАСТРОЙКИ
# Проверяем все варианты имени токена, которые ты создавала на хостинге
TOKEN = os.getenv("BOT_TOKEN") or os.getenv("API_TOKEN") or os.getenv("BOT_API_TOKEN")
GROUP_ID = '207903951'
CHAT_PEER_ID = 2000000491

def start_bot():
    if not TOKEN:
        print("❌ ОШИБКА: Токен не найден в переменных окружения! Проверь настройки на Bothost.")
        return

    try:
        vk_session = vk_api.VkApi(token=TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        
        print(f"✅ БОТ ЗАПУЩЕН!")
        print(f"Слушаю группу: vk.com/club{GROUP_ID}")
        print(f"Цель: чат {CHAT_PEER_ID}")

        for event in longpoll.listen():
            if event.type == VkBotEventType.WALL_POST_NEW:
                post = event.obj
                # Важно: для некоторых версий API структура event.obj может отличаться
                # используем максимально надежный способ получения ID
                post_id = post.get('id')
                owner_id = post.get('owner_id')
                
                attachment = f'wall{owner_id}_{post_id}'
                
                try:
                    vk.messages.send(
                        peer_id=CHAT_PEER_ID,
                        message="📢 Внимание! Новый пост в группе!",
                        attachment=attachment,
                        random_id=0
                    )
                    print(f"🚀 Репост {attachment} отправлен!")
                except Exception as send_error:
                    print(f"❌ Ошибка отправки: {send_error}")
                    
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    start_bot()
