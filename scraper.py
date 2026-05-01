import os
import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
SESSION_STRING = os.environ['SESSION_STRING']
CHANNELS_LIST = os.environ['CHANNELS_LIST']

async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    
    os.makedirs('media', exist_ok=True)
    posts = []
    
    # قراءة القنوات من الـ Secret وفصلها
    channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]

    for channel in channels:
        try:
            print(f"Fetching posts from: {channel}")
            
            # جلب بيانات القناة
            entity = await client.get_entity(channel)
            channel_name = entity.title if hasattr(entity, 'title') else channel

            # سحب آخر 20 بوست
            async for message in client.iter_messages(entity, limit=20):
                media_path = None
                if message.media:
                    file_path = await message.download_media(file='media/')
                    media_path = str(file_path).replace('\\', '/') if file_path else None
                    
                posts.append({
                    'id': message.id,
                    'channel_name': channel_name,
                    'channel_username': channel,
                    'text': message.text if message.text else "",
                    'date': message.date.isoformat(),
                    'media': media_path
                })
        except Exception as e:
            print(f"Error fetching from {channel}: {e}")
            continue

    # ترتيب البوستات زمنياً من الأحدث للأقدم
    posts.sort(key=lambda x: x['date'], reverse=True)

    # حفظ البيانات
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    asyncio.run(main())
