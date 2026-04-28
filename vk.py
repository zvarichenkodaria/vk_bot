import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import os
import time

# --- НАСТРОЙКИ (Берем из переменных окружения хостинга) ---
TOKEN = os.getenv("BOT_TOKEN")        # В настройках хостинга создайте переменную VK_TOKEN
GROUP_ID = '207903951'             # ID вашей группы (только цифры)
CHAT_PEER_ID = 2000000491         # ID вашего чата
# =============================================

def start_bot():
    try:
        # Авторизация
        vk_session = vk_api.VkApi(token=TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        
        print(f"✅ Бот запущен! Слушаю стену группы {GROUP_ID}...")
        print(f"📢 Репосты будут отправляться в чат {CHAT_PEER_ID}")

        for event in longpoll.listen():
            # Если на стене появился новый пост
            if event.type == VkBotEventType.WALL_POST_NEW:
                post = event.obj
                owner_id = post['owner_id']
                post_id = post['id']
                
                # Создаем ссылку-вложение на пост
                attachment = f'wall{owner_id}_{post_id}'
                
                # Текст сообщения (можно добавить @all, если бот админ)
                message_text = "📢 Новый пост в группе!"
                
                try:
                    vk.messages.send(
                        peer_id=CHAT_PEER_ID,
                        message=message_text,
                        attachment=attachment,
                        random_id=0
                    )
                    print(f"--- Репост wall{owner_id}_{post_id} выполнен успешно.")
                except Exception as e:
                    print(f"❌ Ошибка при отправке сообщения: {e}")
                    
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    start_bot()
