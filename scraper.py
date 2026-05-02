# scraper.py
import os
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
POSTS_PER_CHANNEL = 50   # حد أقصى لكل قناة لو القناة جديدة ومفيش بيانات قديمة
TOTAL_LIMIT = 200        # الحد الأقصى للبوستات المحفوظة في data.json
SLEEP_BETWEEN = 1.5
DATA_FILE = 'data.json'
STATS_FILE = 'stats.json'


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
    return 'text'


def extract_hashtags(text):
    """استخراج الهاشتاقات من النص"""
    if not text:
        return []
    import re
    return re.findall(r'#(\w+)', text)


def load_existing_posts():
    """تحميل البوستات القديمة من الملف"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    print(f"📂 تم تحميل {len(data)} بوست قديم من {DATA_FILE}")
                    return data
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ خطأ في قراءة الملف القديم: {e}")

    print("📂 لا يوجد ملف قديم، سيتم إنشاء ملف جديد")
    return []


def get_last_id_per_channel(posts):
    """
    آخر post ID محفوظ لكل قناة
    بيتستخدم كـ min_id عشان نسحب بس الجديد
    """
    last_ids = {}
    for post in posts:
        ch = post.get('channel', '')
        pid = post.get('id', 0)
        if ch not in last_ids or pid > last_ids[ch]:
            last_ids[ch] = pid
    return last_ids


def merge_posts(old_posts, new_posts):
    """
    دمج البوستات القديمة مع الجديدة بدون تكرار
    المفتاح الفريد = channel + id
    لو البوست موجود → يتحدث (مشاهدات، تفاعلات...)
    لو بوست جديد → يتضاف
    في النهاية بيحتفظ بأحدث TOTAL_LIMIT بوست فقط
    """
    posts_map = {}
    for post in old_posts:
        key = f"{post.get('channel', '')}_{post.get('id', '')}"
        posts_map[key] = post

    new_count = 0
    updated_count = 0
    for post in new_posts:
        key = f"{post.get('channel', '')}_{post.get('id', '')}"
        if key in posts_map:
            posts_map[key]['views'] = post.get('views', 0)
            posts_map[key]['forwards'] = post.get('forwards', 0)
            posts_map[key]['reactions'] = post.get('reactions', 0)
            updated_count += 1
        else:
            posts_map[key] = post
            new_count += 1

    print(f"  🆕 بوستات جديدة: {new_count}")
    print(f"  🔄 بوستات محدّثة: {updated_count}")

    # رتب بالأحدث واحتفظ بـ TOTAL_LIMIT بس
    merged = list(posts_map.values())
    merged.sort(key=lambda x: x.get('date', ''), reverse=True)
    merged = merged[:TOTAL_LIMIT]

    return merged


async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    # تحميل البيانات القديمة وعمل index بآخر ID لكل قناة
    old_posts = load_existing_posts()
    last_ids = get_last_id_per_channel(old_posts)

    if last_ids:
        print(f"🔖 عندنا بيانات قديمة لـ {len(last_ids)} قناة، هنسحب الجديد فقط")
    else:
        print(f"🆕 أول رانة، هنسحب آخر {POSTS_PER_CHANNEL} بوست من كل قناة")

    new_posts = []
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

            # لو عندنا آخر ID للقناة دي → اسحب الجديد بس
            # لو قناة جديدة → اسحب آخر POSTS_PER_CHANNEL
            min_id = last_ids.get(channel_title, 0)

            if min_id > 0:
                print(f"  ⏳ {channel_title}: سحب الجديد بعد ID {min_id}...")
            else:
                print(f"  ⏳ {channel_title}: قناة جديدة، سحب آخر {POSTS_PER_CHANNEL} بوست...")

            async for message in client.iter_messages(
                entity,
                min_id=min_id,
                limit=POSTS_PER_CHANNEL  # حماية من قنوات فيها ألاف البوستات الجديدة
            ):
                if username:
                    post_link = f"https://t.me/{username}/{message.id}"
                else:
                    peer_id = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                post_type = detect_post_type(message)
                text = message.text or message.message or ''
                hashtags = extract_hashtags(text)

                views = getattr(message, 'views', 0) or 0
                forwards = getattr(message, 'forwards', 0) or 0

                reactions_count = 0
                if hasattr(message, 'reactions') and message.reactions:
                    for r in message.reactions.results:
                        reactions_count += r.count

                new_posts.append({
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

            if count == 0:
                print(f"  ✅ {channel_title}: مفيش بوستات جديدة")
            else:
                print(f"  ✅ {channel_title}: {count} بوست جديد")

            channel_stats[channel_title] = count
            await asyncio.sleep(SLEEP_BETWEEN)

        except Exception as e:
            print(f"  ❌ خطأ في {getattr(entity, 'title', '?')}: {e}")
            continue

    # ====== الدمج مع البيانات القديمة ======
    print("\n📦 جاري دمج البيانات...")
    merged_posts = merge_posts(old_posts, new_posts)

    print(f"\n📊 الإحصائيات:")
    print(f"  📂 البوستات القديمة: {len(old_posts)}")
    print(f"  📥 البوستات المسحوبة: {len(new_posts)}")
    print(f"  📚 الإجمالي بعد الدمج: {len(merged_posts)} (حد أقصى {TOTAL_LIMIT})")

    # حفظ البوستات
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(merged_posts, f, ensure_ascii=False, indent=2)

    # حفظ الإحصائيات
    stats = {
        'last_update': datetime.utcnow().isoformat(),
        'total_posts': len(merged_posts),
        'channels_count': len(target_entities),
        'channels': channel_stats,
        'types': {},
        'history': {
            'old_posts': len(old_posts),
            'new_scraped': len(new_posts),
            'after_merge': len(merged_posts),
        }
    }
    for p in merged_posts:
        t = p.get('type', 'text')
        stats['types'][t] = stats['types'].get(t, 0) + 1

    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 تم حفظ {len(merged_posts)} بوست بنجاح!")
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
