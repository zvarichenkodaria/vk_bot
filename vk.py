import os
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

# Настройки (из твоих скриншотов)
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = '207903951'
CHAT_PEER_ID = 2000000491

def start_bot():
    print("=== ПОПЫТКА ЗАПУСКА БОТА ===", flush=True)
    
    if not TOKEN:
        print("❌ ОШИБКА: Переменная BOT_TOKEN пуста! Проверь настройки хостинга.", flush=True)
        return

    try:
        vk_session = vk_api.VkApi(token=TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        
        print("✅ БОТ ПОДКЛЮЧИЛСЯ К VK!", flush=True)
        print(f"Слушаю стену группы {GROUP_ID}...", flush=True)

        for event in longpoll.listen():
            # Это покажет ЛЮБОЕ действие в логах
            print(f"Получено событие: {event.type}", flush=True)

            if event.type == VkBotEventType.WALL_POST_NEW:
                # Универсальное получение данных для API 5.199
                post = event.obj.get('wallpost') or event.obj
                post_id = post.get('id')
                owner_id = post.get('owner_id')

                if post_id:
                    attachment = f"wall{owner_id}_{post_id}"
                    print(f"🔎 Вижу новый пост! Пытаюсь отправить в чат {CHAT_PEER_ID}...", flush=True)
                    
                    try:
                        vk.messages.send(
                            peer_id=CHAT_PEER_ID,
                            message="📢 Внимание! Новый пост в группе!",
                            attachment=attachment,
                            random_id=get_random_id()
                        )
                        print(f"🚀 Пост {attachment} успешно отправлен в чат!", flush=True)
                    except Exception as send_err:
                        print(f"❌ Ошибка при отправке: {send_err}", flush=True)

    except Exception as e:
        print(f"❌ КРИТИЧЕСКИЙ СБОЙ: {e}", flush=True)

if __name__ == "__main__":
    start_bot()
