import os
import time
import asyncio
import re
import gc
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
import database as db

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🔥 CRUISE CONTROL (Speed Limit)
SPEED_GOVERNOR = 0.15 

# ================= 🧠 PARSER & CAPTION MAKER 🧠 =================
EP_PATTERN = r"(?:^|[\s\[\(\.\-_])(?:(?:S(?:eason)?\s*(\d{1,3}))(?:[\s\.\-_]*(?:E|EP|Episode)\s*[\.\-_]?\s*(\d{1,4}))?|(?:EP|Episode)\s*[\.\-_]?\s*(\d{1,4})|E(\d{1,4}))(?:[\s\]\)\.\-_]|$)"

def classify_media(text):
    if re.search(EP_PATTERN, text, re.IGNORECASE): return "SERIES"
    return "MOVIE"

def extract_metadata(filename, caption, file_size_bytes):
    text = f"{filename} {caption}"
    meta = {}
    
    source_map = {r'\b(bluray)\b': 'BluRay', r'\b(remux)\b': 'REMUX', r'\b(web-?dl)\b': 'WEB-DL', r'\b(webrip)\b': 'WEBRip', r'\b(hdtv)\b': 'HDTV', r'\b(hdcam)\b': 'HDCAM'}
    sources = [display for pattern, display in source_map.items() if re.search(pattern, text, re.IGNORECASE)]
    meta['Source'] = " / ".join(sources) if sources else None

    codec_map = {r'\b(x265|hevc)\b': 'x265', r'\b(x264|avc)\b': 'x264', r'\b(av1)\b': 'AV1'}
    codecs = [display for pattern, display in codec_map.items() if re.search(pattern, text, re.IGNORECASE)]
    if not codecs:
        fallback_list = ['10Bit', 'HDR', 'DV', 'REMUX', 'BluRay', 'WEB-DL']
        codecs = [tag for tag in fallback_list if re.search(r'(?:^|[^a-zA-Z0-9])' + re.escape(tag) + r'(?:[^a-zA-Z0-9]|$)', text, re.IGNORECASE)]
    meta['Codec'] = " / ".join(codecs[:2]) if codecs else None

    res_map = {r'\b(2160p|4k)\b': '2160p / 4K', r'\b(1080p)\b': '1080p', r'\b(720p)\b': '720p', r'\b(480p)\b': '480p'}
    for pattern, display in res_map.items():
        if re.search(pattern, text, re.IGNORECASE):
            meta['Resolution'] = display
            break
    else: meta['Resolution'] = None

    meta['HDR'] = 'Dolby Vision' if re.search(r'\b(dolby\s*vision|dv)\b', text, re.IGNORECASE) else ('HDR10+' if re.search(r'\b(hdr10\+)\b', text, re.IGNORECASE) else ('HDR' if re.search(r'\b(hdr)\b', text, re.IGNORECASE) else None))
    meta['Video'] = '10Bit' if re.search(r'\b(10-?bit)\b', text, re.IGNORECASE) else None
    meta['Audio'] = 'Dolby Atmos' if re.search(r'\b(dolby\s*atmos)\b', text, re.IGNORECASE) else ('DTS' if re.search(r'\b(dts)\b', text, re.IGNORECASE) else ('AAC' if re.search(r'\b(aac)\b', text, re.IGNORECASE) else None))

    match = re.search(EP_PATTERN, text, re.IGNORECASE)
    if match:
        meta['Season'] = f"S{int(match.group(1)):02d}" if match.group(1) else None
        meta['Episode'] = f"E{int(match.group(2) or match.group(3) or match.group(4)):02d}" if (match.group(2) or match.group(3) or match.group(4)) else None
    else: meta['Season'], meta['Episode'] = None, None

    meta['Format'] = filename.split('.')[-1].upper() if '.' in filename else "FILE"
    size_mb = file_size_bytes / (1024 * 1024)
    meta['Size'] = f"{size_mb / 1024:.2f} GB" if size_mb >= 1024 else f"{size_mb:.2f} MB"

    return meta

def build_cinematic_caption(filename, meta):
    cap = f"{filename}\n━━━━━━━━━━━━━━━━━━━\n"
    cap += f"💾 DB ID: [@LuciferDatabase] | 🌐 Source: {meta['Source'] or 'N/A'}\n"
    cap += f"⚖️ Size: {meta['Size']} | 🎬 Format: {meta['Format']} | ⚙️ Codec: {meta['Codec'] or 'N/A'}\n"
    if meta['Resolution']: cap += f"📺 Resolution: {meta['Resolution']}\n"
    vid_hdr = [f"🎞️ Video: {meta['Video']}" if meta['Video'] else "", f"✨ HDR: {meta['HDR']}" if meta['HDR'] else ""]
    vid_hdr_str = " | ".join(filter(None, vid_hdr))
    if vid_hdr_str: cap += vid_hdr_str + "\n"
    if meta['Audio']: cap += f"🔊 Audio: {meta['Audio']}\n"
    se = [f"📺 Season: {meta['Season']}" if meta['Season'] else "", f"🎬 Episode: {meta['Episode']}" if meta['Episode'] else ""]
    se_str = " | ".join(filter(None, se))
    if se_str: cap += se_str + "\n"
    cap += f"━━━━━━━━━━━━━━━━━━━\n📢 Join: @LuciferDatabase for fast downloads & Database access.\n❓ Need a File? Request: [@RequestLuciferDatabase]\n━━━━━━━━━━━━━━━━━━━"
    return cap

# ================= CORE COPY FUNCTION =================
async def copy_with_bot(bot, dest_id, source_chat, msg_id, caption):
    try:
        await bot.copy_message(chat_id=dest_id, from_chat_id=source_chat, message_id=msg_id, caption=caption)
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            await bot.copy_message(chat_id=dest_id, from_chat_id=source_chat, message_id=msg_id, caption=caption)
            return True
        except Exception: return False
    except Exception: return False

# ================= 🚀 V3.0 CORE ENGINE TASK =================
async def run_sync_task():
    conf = await db.get_config()
    tokens = conf.get("tokens", [])
    task = await db.get_active_task()
    active_source_str = task.get("source")
    movie_dests = task.get("movie_dests", [])
    series_dests = task.get("series_dests", [])
    
    if not active_source_str or not tokens:
        await db.set_engine_status("STOPPED")
        return

    source_chat = int(active_source_str.split(" - ")[0].strip())
    dest_chats = [int(str(d).split(" - ")[0].strip()) for d in (movie_dests + series_dests)]
    all_chats_to_cache = list(set([source_chat] + dest_chats))

    os.makedirs("sessions", exist_ok=True)
    bots = []
    
    max_bots = min(20, len(tokens)) 
    print(f"🔄 Logging in {max_bots} Worker Bots (Disk Session Mode)...")
    
    for i in range(max_bots):
        try:
            # 🔥 FIX 1: in_memory=True HATA DIYA taaki cache permanent rahe!
            bot = Client(f"sessions/engine_bot_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=tokens[i])
            
            # 🔥 FIX 2: BOTS KO KAAN (EARS) DE DIYE! Ab ping message turant cache ho jayega!
            @bot.on_message(filters.chat(all_chats_to_cache))
            async def cache_catcher(client, message):
                pass
                
            await bot.start()
            bots.append(bot)
            await asyncio.sleep(0.5)
        except Exception as e: 
            print(f"⚠️ Bot {i} failed to connect: {e}")
            
    if not bots: 
        await db.set_engine_status("STOPPED")
        return
    fetch_bot = bots[0]
    
    for b in bots:
        for c in all_chats_to_cache:
            try: await b.get_chat(c)
            except: pass

    end_msg_id = 1800000 
    try:
        async for latest_msg in fetch_bot.get_chat_history(source_chat, limit=1):
            end_msg_id = latest_msg.id
    except Exception: pass

    last_copied = await db.get_last_copied_msg_id(source_chat)
    current_msg_id = (last_copied + 1) if last_copied else 1
    
    total_files = end_msg_id - current_msg_id
    processed_count = 0
    success_count = 0
    failed_count = 0
    last_file_name = "Reading Channel..."
    
    start_time = time.time() 
    await db.update_progress(total_files, processed_count, success_count, failed_count, last_file_name, start_time)

    semaphore = asyncio.Semaphore(len(bots) * 2)
    bot_index = 0

    print(f"🚀 ENGINE RUNNING WITH {len(bots)} ACTIVE BOTS!")

    while current_msg_id <= end_msg_id:
        status = await db.get_engine_status()
        if status == "STOPPED": break
        if status == "PAUSED":
            await asyncio.sleep(2)
            continue

        # 🔥 FIX 3: AB 20 NAHI, SEEDHA 200 MESSAGES EK SATH SCAN KAREGA!
        chunk_end = min(current_msg_id + 199, end_msg_id)
        message_ids_to_fetch = list(range(current_msg_id, chunk_end + 1))
        
        try:
            messages = await fetch_bot.get_messages(source_chat, message_ids_to_fetch)
            
            if not messages:
                current_msg_id = chunk_end + 1
                processed_count += len(message_ids_to_fetch)
                failed_count += len(message_ids_to_fetch)
                await db.mark_file_copied(source_chat, chunk_end)
                continue

            copied_in_this_chunk = False

            for msg in messages:
                processed_count += 1
                if msg.empty or not (msg.video or msg.document):
                    failed_count += 1
                    continue
                
                copied_in_this_chunk = True
                media = msg.document or msg.video
                raw_filename = getattr(media, 'file_name', None) or (msg.caption[:50] if msg.caption else "Unknown Media")
                
                if "." in raw_filename:
                    name_part = raw_filename.rsplit(".", 1)[0]
                    ext = raw_filename.rsplit(".", 1)[-1]
                    filename = name_part.replace("_", " ") + "." + ext
                else:
                    filename = raw_filename.replace("_", " ")

                msg_caption = msg.caption or ""
                f_size = media.file_size or 0
                last_file_name = filename[:35] + "..." 
                
                classification = classify_media(f"{filename} {msg_caption}")
                target_dest_list = series_dests if classification == "SERIES" else movie_dests
                target_chats = [int(str(d).split(" - ")[0].strip()) for d in target_dest_list]
                
                if target_chats:
                    meta = extract_metadata(filename, msg_caption, f_size)
                    naya_caption = build_cinematic_caption(filename, meta)
                    
                    async with semaphore:
                        tasks = []
                        for dest_id in target_chats:
                            worker_bot = bots[bot_index % len(bots)]
                            tasks.append(asyncio.create_task(copy_with_bot(worker_bot, dest_id, source_chat, msg.id, naya_caption)))
                            bot_index += 1
                            await asyncio.sleep(0.02)
                            
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        if any(res is True for res in results): success_count += 1
                        else: failed_count += 1
                            
                # Har file ke baad database hit karna band, ab end mein karenge
                
            # 🔥 Database ko sirf chunk ke end me update karenge taaki speed 100x rahe!
            await db.mark_file_copied(source_chat, chunk_end)
            await db.update_progress(total_files, processed_count, success_count, failed_count, last_file_name, start_time)
            current_msg_id = chunk_end + 1
            
            if copied_in_this_chunk:
                await asyncio.sleep(SPEED_GOVERNOR)
            else:
                # Agar saare 200 messages deleted/khali the, toh rocket ki tarah aage bhago!
                await asyncio.sleep(0.2)
            
            del messages
            gc.collect() 
            
        except Exception as e:
            error_msg = str(e).lower()
            if "peer id invalid" in error_msg or "peer_id_invalid" in error_msg:
                # 🔥 FIX 4: DASHBOARD PE ALERT BHEJEGA!
                await db.update_progress(total_files, processed_count, success_count, failed_count, "⚠️ PING REQUIRED! SEND '.' IN CHANNELS NOW!", start_time)
                print("⚠️ Cache Lost! SEND A MESSAGE IN THE CHANNEL NOW... 🛠️")
                for b in bots:
                    for c in all_chats_to_cache:
                        try: await b.get_chat(c)
                        except: pass
                await asyncio.sleep(5)
            else:
                current_msg_id = chunk_end + 1
                await asyncio.sleep(2)

    if status != "STOPPED":
        await db.set_engine_status("STOPPED")
        
# ================= 🧟 DAEMON LOOP =================
async def main():
    while True:
        status = await db.get_engine_status()
        if status == "RUNNING": await run_sync_task()
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
