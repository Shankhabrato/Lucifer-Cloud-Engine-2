import os
import time
import asyncio
import re
import gc
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.errors import FloodWait
import database as db

load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
BOT_TOKEN = os.getenv("BOT_TOKEN")

EP_PATTERN = r"(?:^|[\s\[\(\.\-_])(?:(?:S(?:eason)?\s*(\d{1,3}))(?:[\s\.\-_]*(?:E|EP|Episode)\s*[\.\-_]?\s*(\d{1,4}))?|(?:EP|Episode)\s*[\.\-_]?\s*(\d{1,4})|E(\d{1,4}))(?:[\s\]\)\.\-_]|$)"

def classify_media(text):
    if re.search(EP_PATTERN, text, re.IGNORECASE): return "SERIES"
    return "MOVIE"

async def copy_with_bot(bot, dest_id, source_chat, msg_id):
    try:
        await bot.copy_message(chat_id=dest_id, from_chat_id=source_chat, message_id=msg_id)
        return True
    except FloodWait as e:
        await asyncio.sleep(e.value)
        try:
            await bot.copy_message(chat_id=dest_id, from_chat_id=source_chat, message_id=msg_id)
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
    
    # 🔒 SEVALLA OOM FIX: Safe Network Sockets & In-Memory Login
    max_bots = min(30, len(tokens)) 
    print(f"🔄 Logging in {max_bots} Worker Bots (Safe Network Mode)...")
    for i in range(max_bots):
        try:
            # in_memory=True se file lock nahi hoga
            bot = Client(f"engine_bot_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=tokens[i], in_memory=True)
            await bot.start()
            bots.append(bot)
            # 1 second ka delay Telegram block aur socket crash ko rokega
            await asyncio.sleep(1)
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

    # 🔒 RAM OPTIMIZATION: Max 7 active copies at once
    semaphore = asyncio.Semaphore(len(bots) * 2)
    bot_index = 0

    print(f"🚀 ENGINE RUNNING WITH {len(bots)} ACTIVE BOTS (RAM Optimized)!")

    while current_msg_id <= end_msg_id:
        status = await db.get_engine_status()
        if status == "STOPPED": break
        if status == "PAUSED":
            await asyncio.sleep(2)
            continue

        chunk_end = min(current_msg_id + 19, end_msg_id)
        message_ids_to_fetch = list(range(current_msg_id, chunk_end + 1))
        
        try:
            messages = await fetch_bot.get_messages(source_chat, message_ids_to_fetch)
            
            if not messages:
                current_msg_id = chunk_end + 1
                continue

            for msg in messages:
                processed_count += 1
                if msg.empty or not (msg.video or msg.document):
                    failed_count += 1
                    await db.mark_file_copied(source_chat, msg.id)
                    continue
                
                media = msg.document or msg.video
                filename = getattr(media, 'file_name', None) or (msg.caption[:30] if msg.caption else "Unknown")
                last_file_name = filename[:35] + "..." 
                
                classification = classify_media(filename)
                target_dest_list = series_dests if classification == "SERIES" else movie_dests
                target_chats = [int(str(d).split(" - ")[0].strip()) for d in target_dest_list]
                
                if target_chats:
                    tasks = []
                    for dest_id in target_chats:
                        worker_bot = bots[bot_index % len(bots)]
                        tasks.append(copy_with_bot(worker_bot, dest_id, source_chat, msg.id))
                        bot_index += 1
                        
                    async with semaphore:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        if any(res is True for res in results): success_count += 1
                        else: failed_count += 1
                            
                await db.mark_file_copied(source_chat, msg.id)
                
            await db.update_progress(total_files, processed_count, success_count, failed_count, last_file_name, start_time)
            current_msg_id = chunk_end + 1
            
            del messages
            gc.collect() 
            
        except Exception as e:
            error_msg = str(e).lower()
            if "peer id invalid" in error_msg or "peer_id_invalid" in error_msg:
                print("⚠️ Cache Lost! Auto-Healing BOTS... 🛠️")
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
