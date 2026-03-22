import asyncio
import logging
import re
import hashlib
import os
from collections import deque
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ================== SOZLAMALAR (Environment Variables) ==================
API_ID = int(os.getenv("API_ID", "34696814"))
API_HASH = os.getenv("API_HASH", "f6c213e017169b70c8465143d1751ea2")
SESSION_STRING = os.getenv("SESSION_STRING")

ADMIN_ID = 5747999018 
SOURCE_CHANNELS = [
    "@Rasmiy_xabarlar_Official", "@shoubizyangiliklari", 
    "@huquqiyaxborot", "@uzb_meteo", "@xavfsizlik_uz", 
    "@qisqasitv", "@Jizzax_Haydovchilari", "@bankxabar", 
    "@Jurnalist24uz", "@Jizzax24kanal"
]
TARGET_CHANNEL = "@Sangzoruz1"
TARGET_LINK = "https://t.me/Sangzoruz1"

POST_INTERVAL = 600 
BATCH_SIZE = 5 
message_queue = deque()
processed_hashes = deque(maxlen=300)

# ================== FILTRLAR ==================

def is_commercial_ad(text):
    """Tijoriy reklamalarni aniqlash (Kafe, Uy, Sotiladi)"""
    if not text: return False
    # Reklama kalit so'zlari
    ad_keywords = [
        r"sotiladi", r"яшаш шароити", r"ижара", r"манзил:", r"мўлжал", 
        r"ошхона", r"кафе", r"ресторан", r"buyurtma berish", r"етказиб бериш",
        r"тел:", r"moshina", r"лизинг", r"кредит", r"хонадон", r"уй сотилади"
    ]
    for word in ad_keywords:
        if re.search(word, text, re.IGNORECASE):
            return True
    return False

def clean_ads(text):
    if not text: return ""
    
    # 1. Havolalar va Usernamelarni butunlay yo'qotish
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'@\w+', '', text)
    
    # 2. Maxsus belgilarni tozalash (⚡️, 👇, ❗, 👈)
    text = re.sub(r'[⚡️👇❗👈👉✅🔹🔸➖]|\-\-\-', '', text)
    
    # 3. Siz aytgan murakkab jumlalar (Kirill va Lotin)
    ad_patterns = [
        r"Каналга обуна бўлинг", r"мухим хабарларни биринчи ўқинг", 
        r"энг тезкор хабарлар канали", r"аъзо бўлинг", r"Sahifalarimizga obuna bo‘ling",
        r"Медиабанк", r"Facebook", r"TikTok", r"Instagram", r"YouTube", r"X.com",
        r"YouTube", r"t.me", r"obuna bo'ling", r"reklama", r"САҚЛАБ ОЛИНГ",
        r"ЯҚИНЛАРГА ЮБОРИБ ҚЎЙИНГ", r"саҳифаларимизга", r"obuna bo‘ling"
    ]
    
    for pattern in ad_patterns:
        text = re.compile(pattern, re.IGNORECASE).sub("", text)
    
    # 4. Ortiqcha qatorlar va bo'shliqlarni tozalash
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def get_message_hash(event):
    """Xabar mazmunidan hash olish (dublikatni oldini olish)"""
    content = ""
    if event.message.message:
        # Matnning boshidagi 50 ta harfni olamiz (reklamadan tozalangan holda)
        clean_txt = clean_ads(event.message.message)[:50].lower()
        content += clean_txt
    if event.message.media:
        if hasattr(event.message.media, 'document'):
            content += str(event.message.media.document.size)
        elif hasattr(event.message.media, 'photo'):
            content += str(event.message.media.photo.id)
    return hashlib.md5(content.encode()).hexdigest()

# ================== NAVBATNI BOSHQARISH ==================

async def post_manager():
    await asyncio.sleep(10)
    while True:
        if message_queue:
            for _ in range(BATCH_SIZE):
                if not message_queue: break
                
                msg_event = message_queue.popleft()
                raw_text = msg_event.message.message
                
                # Agar tijoriy reklama bo'lsa, tashlab ketamiz
                if is_commercial_ad(raw_text):
                    logging.info("🛑 Tijoriy reklama (osh/uy/kafe) aniqlandi, yuborilmadi.")
                    continue

                clean_text = clean_ads(raw_text)
                # Agar matn tozalashdan keyin bo'sh bo'lib qolsa, "Yangilik" deb qo'yamiz
                final_text = clean_text if clean_text else "Yangilik"
                final_text += f"\n\n👉 <a href='{TARGET_LINK}'>Sangzoruz1 - Kanalga obuna bo'ling</a>"
                
                try:
                    if msg_event.message.media:
                        # Media fayllarni pereslat qilmaymiz, yuklab qayta jo'natamiz (reklama linklari ketmasligi uchun)
                        await client.send_file(TARGET_CHANNEL, msg_event.message.media, caption=final_text, parse_mode='html')
                    else:
                        await client.send_message(TARGET_CHANNEL, final_text, parse_mode='html', link_preview=False)
                    logging.info("✅ OK: Xabar kanalga yuborildi.")
                except Exception as e:
                    logging.error(f"❌ Xato: {e}")
                
                await asyncio.sleep(4)
            await asyncio.sleep(POST_INTERVAL)
        else:
            await asyncio.sleep(20)

# ================== TELEGRAM HANDLER ==================

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    # Faqat Rasm, Video yoki Matn bo'lsa olamiz
    has_media = event.message.photo or event.message.video
    has_text = event.message.message and len(event.message.message) > 5

    if has_media or has_text:
        # Dublikat tekshiruvi
        m_hash = get_message_hash(event)
        if m_hash in processed_hashes:
            logging.info("♻️ Dublikat xabar (rad etildi).")
            return
        
        processed_hashes.append(m_hash)
        message_queue.append(event)
        logging.info(f"📩 Yangi xabar navbatga olindi. (Navbat: {len(message_queue)})")

async def main():
    await client.start()
    print("🚀 Bot ishlamoqda. Reklama va dublikatlar filtrlanadi...")
    client.loop.create_task(post_manager())
    await client.run_until_disconnected()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
