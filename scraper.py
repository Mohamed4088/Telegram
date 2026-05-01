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
    print("[*] جاري الاتصال بحساب تليجرام...")
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("[+] تم الاتصال بنجاح!")
    
    posts = []
    
    # 1. تنظيف قائمة القنوات المستهدفة (تحويلها لمعرفات نظيفة)
    raw_channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]
    target_identifiers = []
    for ch in raw_channels:
        clean_ch = ch.replace('https://t.me/', '').replace('@', '').replace('joinchat/', '').strip().lower()
        target_identifiers.append(clean_ch)
        
    print(f"[*] المعرفات المستهدفة: {len(target_identifiers)} قناة")

    # 2. سحب قائمة القنوات التي أنت مشترك فيها (لتخطي حظر البحث)
    print("[*] جاري جلب محادثاتك الحالية (لتجنب حظر تليجرام)...")
    dialogs = await client.get_dialogs()
    
    target_entities = []
    for dialog in dialogs:
        if dialog.is_channel or dialog.is_group:
            entity = dialog.entity
            username = getattr(entity, 'username', None)
            channel_id_str = str(entity.id).replace('-100', '')
            
            # فلترة القنوات لتطابق القائمة الخاصة بك
            if (username and username.lower() in target_identifiers) or \
               (channel_id_str in target_identifiers):
                target_entities.append(entity)

    if not target_entities:
        print("[!] لم يتم العثور على أي قناة مطابقة داخل اشتراكاتك.")
        sys.exit(1)

    print(f"[+] تم العثور على {len(target_entities)} قناة جاهزة للسحب.")

    # 3. سحب البوستات
    for entity in target_entities:
        channel_title = entity.title if hasattr(entity, 'title') else "Private Channel"
        try:
            print(f"----------------------------------------")
            print(f"[*] سحب البيانات من: {channel_title}")
            
            count = 0
            async for message in client.iter_messages(entity, limit=20): # قللنا العدد لـ 20 لتخفيف الضغط
                if getattr(entity, 'username', None):
                    post_link = f"https://t.me/{entity.username}/{message.id}"
                else:
                    peer_id = str(entity.id).replace("-100", "")
                    post_link = f"https://t.me/c/{peer_id}/{message.id}"

                posts.append({
                    'id': message.id,
                    'channel': channel_title,
                    'text': message.text if message.text else "[ميديا أو رسالة فارغة]",
                    'date': message.date.isoformat(),
                    'link': post_link
                })
                count += 1
            
            print(f"[+] تم سحب {count} بوست من {channel_title}")
            
            # หน่วงเวลา 2 ثانية بين كل قناة وأخرى لعدم إثارة أنظمة تليجرام
            await asyncio.sleep(2) 
            
        except Exception as e:
            print(f"[!] فشل السحب من {channel_title} - السبب: {e}")

    posts.sort(key=lambda x: x['date'], reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
    await client.disconnect()

    if not posts:
        print("\n[!!!] خطأ حرج: لم يتم سحب أي بوست.")
        sys.exit(1)
    else:
        print(f"\n[=] تمت العملية بنجاح! إجمالي البوستات: {len(posts)}")

if __name__ == '__main__':
    asyncio.run(main())
