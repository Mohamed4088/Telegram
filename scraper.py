import os
import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
SESSION_STRING = os.environ['SESSION_STRING']
CHANNELS_LIST = os.environ['CHANNELS_LIST']

async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    
    posts = []
    channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]

    for channel_input in channels:
        try:
            print(f"Processing: {channel_input}")
            entity = await client.get_entity(channel_input)
            
            # تحديد اسم القناة والرابط الأساسي
            channel_title = entity.title if hasattr(entity, 'title') else "Private Channel"
            
            async for message in client.iter_messages(entity, limit=30):
                # إنشاء رابط البوست
                if isinstance(entity, Channel) and entity.username:
                    post_link = f"https://t.me/{entity.username}/{message.id}"
                else:
                    # للقنوات الخاصة التي لا تملك Username
                    peer_id = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                posts.append({
                    'id': message.id,
                    'channel': channel_title,
                    'text': message.text if message.text else "[وسائط أو رسالة فارغة]",
                    'date': message.date.isoformat(),
                    'link': post_link
                })
        except Exception as e:
            print(f"Error with {channel_input}: {e}")

    # الترتيب من الأحدث
    posts.sort(key=lambda x: x['date'], reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
