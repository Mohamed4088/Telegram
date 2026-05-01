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
    channels = [ch.strip() for ch in CHANNELS_LIST.split(',') if ch.strip()]
    print(f"[*] القنوات التي تم قراءتها من الـ Secret: {channels}")

    if not channels:
        print("[!] خطأ: الـ Secret الخاص بالقنوات فارغ أو لم يتم قراءته بشكل صحيح.")
        sys.exit(1)

    for channel_input in channels:
        try:
            print(f"----------------------------------------")
            print(f"[*] محاولة سحب البيانات من: {channel_input}")
            
            # معالجة الروابط لو المستخدم حط لينك كامل بدل الـ Username
            target = channel_input
            if "t.me/" in target:
                parts = target.split("t.me/")[1].split("/")
                if not target.startswith("+") and "joinchat" not in target:
                    target = parts[0]
            
            # تحويل الأرقام (IDs) إلى Integer لأن Telethon يطلبها هكذا للقنوات الخاصة
            try:
                target = int(target)
            except ValueError:
                pass

            entity = await client.get_entity(target)
            channel_title = entity.title if hasattr(entity, 'title') else str(target)
            
            count = 0
            async for message in client.iter_messages(entity, limit=30):
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
            
        except Exception as e:
            print(f"[!] فشل السحب من {channel_input} - السبب: {e}")

    posts.sort(key=lambda x: x['date'], reverse=True)

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)
    
    await client.disconnect()

    # لو القائمة فاضية بعد كل ده، ارمي خطأ عشان الـ Action يقف ونشوف الـ Logs
    if not posts:
        print("\n[!!!] خطأ حرج: لم يتم سحب أي بوست من أي قناة. تأكد من الروابط أو صلاحية الجلسة.")
        sys.exit(1)
    else:
        print(f"\n[=] تمت العملية بنجاح! إجمالي البوستات المسحوبة: {len(posts)}")

if __name__ == '__main__':
    asyncio.run(main())
