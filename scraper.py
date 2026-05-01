import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
SESSION_STRING = os.environ['SESSION_STRING']
CHANNELS_LIST = os.environ.get('CHANNELS_LIST', '')

async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    
    posts = []
    raw_channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]
    target_identifiers = [ch.replace('https://t.me/', '').replace('@', '').lower() for ch in raw_channels]

    dialogs = await client.get_dialogs()
    target_entities = []
    for dialog in dialogs:
        if dialog.is_channel or dialog.is_group:
            entity = dialog.entity
            username = getattr(entity, 'username', None)
            channel_id_str = str(entity.id).replace('-100', '')
            if (username and username.lower() in target_identifiers) or (channel_id_str in target_identifiers):
                target_entities.append(entity)

    for entity in target_entities:
        try:
            channel_title = entity.title if hasattr(entity, 'title') else "Private"
            # سحب آخر 15 بوست من كل قناة لتقليل الحجم الكلي
            async for message in client.iter_messages(entity, limit=15):
                if getattr(entity, 'username', None):
                    post_link = f"https://t.me/{entity.username}/{message.id}"
                else:
                    peer_id = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                posts.append({
                    'channel': channel_title,
                    'text': message.text if message.text else "[ميديا فقط]",
                    'date': message.date.isoformat(),
                    'link': post_link
                })
            await asyncio.sleep(1) # حماية من الحظر
        except: continue

    # ترتيب الأحدث ثم الاكتفاء بآخر 100 بوست فقط للموقع كله
    posts.sort(key=lambda x: x['date'], reverse=True)
    final_posts = posts[:100] 

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_posts, f, ensure_ascii=False, indent=4)
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
