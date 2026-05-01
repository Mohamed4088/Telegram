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
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, connection_retries=5)
    await client.start()
    
    posts = []
    channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]

    for channel in channels:
        try:
            entity = await client.get_entity(channel)
            channel_name = entity.title if hasattr(entity, 'title') else str(channel)
            
            # تحديد نوع القناة لبناء الرابط الصحيح
            is_public = True if getattr(entity, 'username', None) else False

            # سحب آخر 50 بوست لكل قناة
            async for message in client.iter_messages(entity, limit=50):
                # تجاهل رسائل النظام الفارغة
                if not message.message and not message.media:
                    continue

                # بناء الرابط المباشر للبوست
                if is_public:
                    post_link = f"https://t.me/{entity.username}/{message.id}"
                else:
                    # معرفات القنوات الخاصة تبدأ بـ -100 في API تليجرام، يتم إزالتها في روابط الويب
                    clean_id = str(entity.id).replace('-100', '')
                    post_link = f"https://t.me/c/{clean_id}/{message.id}"

                # تعويض النص إذا كان البوست عبارة عن صورة/ملف بدون تعليق
                post_text = message.message if message.message else "📎 [يحتوي على مرفقات - افتح الرابط للمشاهدة]"

                posts.append({
                    'id': message.id,
                    'channel_name': channel_name,
                    'text': post_text,
                    'date': message.date.isoformat(),
                    'link': post_link
                })
        except Exception as e:
            print(f"Error fetching {channel}: {e}")
            continue

    # الترتيب من الأحدث للأقدم
    posts.sort(key=lambda x: x['date'], reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
