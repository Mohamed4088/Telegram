# scraper.py
import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
SESSION_STRING = os.environ['SESSION_STRING']
CHANNELS_LIST = os.environ.get('CHANNELS_LIST', '')

# ====== الإعدادات ======
POSTS_PER_CHANNEL = 50      # عدد البوستات من كل قناة
MAX_TOTAL_POSTS = 500       # الحد الأقصى الكلي
SLEEP_BETWEEN = 1.5         # ثواني انتظار بين القنوات


def detect_post_type(message):
    """تحديد نوع البوست بدقة"""
    if message.photo:
        return 'photo'
    elif message.video:
        return 'video'
    elif message.document:
        mime = getattr(message.document, 'mime_type', '') or ''
        if 'pdf' in mime:
            return 'pdf'
        elif 'image' in mime:
            return 'photo'
        elif 'video' in mime:
            return 'video'
        return 'document'
    elif message.voice:
        return 'voice'
    elif message.video_note:
        return 'video_note'
    elif message.sticker:
        return 'sticker'
    elif message.poll:
        return 'poll'
    elif message.geo:
        return 'location'
    elif message.contact:
        return 'contact'
    elif getattr(message, 'forward', None):
        return 'forwarded'
    return 'text'


def extract_hashtags(text):
    """استخراج الهاشتاقات من النص"""
    if not text:
        return []
    import re
    return re.findall(r'#(\w+)', text)


async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    posts = []
    channel_stats = {}

    raw_channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]
    target_identifiers = [
        ch.replace('https://t.me/', '').replace('@', '').lower()
        for ch in raw_channels
    ]

    dialogs = await client.get_dialogs()
    target_entities = []

    for dialog in dialogs:
        if dialog.is_channel or dialog.is_group:
            entity = dialog.entity
            username = getattr(entity, 'username', None)
            channel_id_str = str(entity.id).replace('-100', '')

            if (username and username.lower() in target_identifiers) or \
               (channel_id_str in target_identifiers):
                target_entities.append(entity)

    print(f"📡 تم العثور على {len(target_entities)} قناة من أصل {len(raw_channels)}")

    for entity in target_entities:
        try:
            channel_title = getattr(entity, 'title', 'Private')
            username = getattr(entity, 'username', None)
            count = 0

            print(f"  ⏳ جاري سحب بوستات: {channel_title}...")

            async for message in client.iter_messages(entity, limit=POSTS_PER_CHANNEL):
                # بناء رابط البوست
                if username:
                    post_link = f"https://t.me/{username}/{message.id}"
                else:
                    peer_id = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                # تحديد النوع
                post_type = detect_post_type(message)

                # استخراج النص
                text = message.text or message.message or ''
                caption = ''
                if not text and hasattr(message, 'message') and message.message:
                    text = message.message

                # استخراج الهاشتاقات
                hashtags = extract_hashtags(text)

                # عدد المشاهدات والتفاعلات
                views = getattr(message, 'views', 0) or 0
                forwards = getattr(message, 'forwards', 0) or 0

                # التفاعلات (Reactions)
                reactions_count = 0
                if hasattr(message, 'reactions') and message.reactions:
                    for r in message.reactions.results:
                        reactions_count += r.count

                posts.append({
                    'id': message.id,
                    'channel': channel_title,
                    'channel_username': username or '',
                    'text': text if text else '[ميديا فقط]',
                    'type': post_type,
                    'date': message.date.isoformat(),
                    'link': post_link,
                    'views': views,
                    'forwards': forwards,
                    'reactions': reactions_count,
                    'hashtags': hashtags,
                    'has_media': post_type != 'text',
                    'is_forwarded': bool(getattr(message, 'forward', None)),
                })
                count += 1

            channel_stats[channel_title] = count
            print(f"  ✅ {channel_title}: {count} بوست")
            await asyncio.sleep(SLEEP_BETWEEN)

        except Exception as e:
            print(f"  ❌ خطأ في {channel_title}: {e}")
            continue

    # ترتيب بالأحدث
    posts.sort(key=lambda x: x['date'], reverse=True)
    final_posts = posts[:MAX_TOTAL_POSTS]

    # حفظ البوستات
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(final_posts, f, ensure_ascii=False, indent=2)

    # حفظ الإحصائيات
    stats = {
        'last_update': datetime.utcnow().isoformat(),
        'total_posts': len(final_posts),
        'channels_count': len(target_entities),
        'channels': channel_stats,
        'types': {},
    }
    for p in final_posts:
        t = p['type']
        stats['types'][t] = stats['types'].get(t, 0) + 1

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 تم حفظ {len(final_posts)} بوست + الإحصائيات")
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
