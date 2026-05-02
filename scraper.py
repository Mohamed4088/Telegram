# scraper.py
import os
import json
import math
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
SESSION_STRING = os.environ['SESSION_STRING']
CHANNELS_LIST = os.environ.get('CHANNELS_LIST', '')

# ====== الإعدادات ======
POSTS_PER_CHANNEL = 50    # حد أقصى لكل قناة لو قناة جديدة
TOTAL_LIMIT       = 50000 # الحد الأقصى للأرشيف الكامل
DISPLAY_PER_PAGE  = 200   # عدد البوستات في كل صفحة للـ HTML
SLEEP_BETWEEN     = 1.5
ARCHIVE_FILE      = 'archive.json'
STATS_FILE        = 'stats.json'


def detect_post_type(message):
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
    return 'text'


def extract_hashtags(text):
    if not text:
        return []
    import re
    return re.findall(r'#(\w+)', text)


def load_existing_posts():
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    print(f"📂 تم تحميل {len(data)} بوست من الأرشيف")
                    return data
        except Exception as e:
            print(f"⚠️ خطأ في قراءة الأرشيف: {e}")
    print("📂 لا يوجد أرشيف قديم، سيتم إنشاء أرشيف جديد")
    return []


def get_last_id_per_channel(posts):
    last_ids = {}
    for post in posts:
        ch  = post.get('channel', '')
        pid = post.get('id', 0)
        if ch not in last_ids or pid > last_ids[ch]:
            last_ids[ch] = pid
    return last_ids


def merge_posts(old_posts, new_posts):
    posts_map = {}
    for post in old_posts:
        key = f"{post.get('channel', '')}_{post.get('id', '')}"
        posts_map[key] = post

    new_count     = 0
    updated_count = 0
    for post in new_posts:
        key = f"{post.get('channel', '')}_{post.get('id', '')}"
        if key in posts_map:
            posts_map[key]['views']     = post.get('views', 0)
            posts_map[key]['forwards']  = post.get('forwards', 0)
            posts_map[key]['reactions'] = post.get('reactions', 0)
            updated_count += 1
        else:
            posts_map[key] = post
            new_count += 1

    print(f"  🆕 بوستات جديدة: {new_count}")
    print(f"  🔄 بوستات محدّثة: {updated_count}")

    merged = list(posts_map.values())
    merged.sort(key=lambda x: x.get('date', ''), reverse=True)
    merged = merged[:TOTAL_LIMIT]
    return merged


def save_pages(merged_posts):
    # 1) الأرشيف الكامل
    with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged_posts, f, ensure_ascii=False, indent=2)
    print(f"💾 تم حفظ الأرشيف الكامل: {len(merged_posts)} بوست")

    # 2) تقسيم لصفحات
    total_pages = max(1, math.ceil(len(merged_posts) / DISPLAY_PER_PAGE))
    for i in range(total_pages):
        chunk    = merged_posts[i * DISPLAY_PER_PAGE:(i + 1) * DISPLAY_PER_PAGE]
        filename = f'data_page_{i + 1}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

    print(f"📄 تم إنشاء {total_pages} صفحة (كل صفحة {DISPLAY_PER_PAGE} بوست)")
    return total_pages


async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    old_posts = load_existing_posts()
    last_ids  = get_last_id_per_channel(old_posts)

    if last_ids:
        print(f"🔖 عندنا أرشيف لـ {len(last_ids)} قناة، هنسحب الجديد فقط")
    else:
        print(f"🆕 أول رانة، هنسحب آخر {POSTS_PER_CHANNEL} بوست من كل قناة")

    new_posts     = []
    channel_stats = {}

    raw_channels        = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]
    target_identifiers  = [
        ch.replace('https://t.me/', '').replace('@', '').lower()
        for ch in raw_channels
    ]

    dialogs         = await client.get_dialogs()
    target_entities = []

    for dialog in dialogs:
        if dialog.is_channel or dialog.is_group:
            entity         = dialog.entity
            username       = getattr(entity, 'username', None)
            channel_id_str = str(entity.id).replace('-100', '')
            if (username and username.lower() in target_identifiers) or \
               (channel_id_str in target_identifiers):
                target_entities.append(entity)

    print(f"📡 تم العثور على {len(target_entities)} قناة من أصل {len(raw_channels)}")

    for entity in target_entities:
        try:
            channel_title = getattr(entity, 'title', 'Private')
            username      = getattr(entity, 'username', None)
            count         = 0
            min_id        = last_ids.get(channel_title, 0)

            if min_id > 0:
                print(f"  ⏳ {channel_title}: سحب الجديد بعد ID {min_id}...")
            else:
                print(f"  ⏳ {channel_title}: قناة جديدة، سحب آخر {POSTS_PER_CHANNEL} بوست...")

            async for message in client.iter_messages(entity, min_id=min_id, limit=POSTS_PER_CHANNEL):
                if username:
                    post_link = f"https://t.me/{username}/{message.id}"
                else:
                    peer_id   = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                post_type = detect_post_type(message)
                text      = message.text or message.message or ''
                hashtags  = extract_hashtags(text)
                views     = getattr(message, 'views', 0) or 0
                forwards  = getattr(message, 'forwards', 0) or 0

                reactions_count = 0
                if hasattr(message, 'reactions') and message.reactions:
                    for r in message.reactions.results:
                        reactions_count += r.count

                new_posts.append({
                    'id':               message.id,
                    'channel':          channel_title,
                    'channel_username': username or '',
                    'text':             text if text else '[ميديا فقط]',
                    'type':             post_type,
                    'date':             message.date.isoformat(),
                    'link':             post_link,
                    'views':            views,
                    'forwards':         forwards,
                    'reactions':        reactions_count,
                    'hashtags':         hashtags,
                    'has_media':        post_type != 'text',
                    'is_forwarded':     bool(getattr(message, 'forward', None)),
                })
                count += 1

            if count == 0:
                print(f"  ✅ {channel_title}: مفيش بوستات جديدة")
            else:
                print(f"  ✅ {channel_title}: {count} بوست جديد")

            channel_stats[channel_title] = count
            await asyncio.sleep(SLEEP_BETWEEN)

        except Exception as e:
            print(f"  ❌ خطأ في {getattr(entity, 'title', '?')}: {e}")
            continue

    print("\n📦 جاري دمج البيانات...")
    merged_posts = merge_posts(old_posts, new_posts)

    print(f"\n📊 الإحصائيات:")
    print(f"  📂 البوستات القديمة:  {len(old_posts)}")
    print(f"  📥 البوستات المسحوبة: {len(new_posts)}")
    print(f"  📚 الإجمالي:          {len(merged_posts)}")

    total_pages = save_pages(merged_posts)

    stats = {
        'last_update':    datetime.utcnow().isoformat(),
        'total_posts':    len(merged_posts),
        'total_pages':    total_pages,
        'per_page':       DISPLAY_PER_PAGE,
        'channels_count': len(target_entities),
        'channels':       channel_stats,
        'types':          {},
        'history': {
            'old_posts':   len(old_posts),
            'new_scraped': len(new_posts),
            'after_merge': len(merged_posts),
        }
    }
    for p in merged_posts:
        t = p.get('type', 'text')
        stats['types'][t] = stats['types'].get(t, 0) + 1

    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 تم! {len(merged_posts)} بوست في {total_pages} صفحة")
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
