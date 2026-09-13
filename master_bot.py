import os
import asyncio
import time
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

app = Client("master_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_arg(message):
    return message.text.split(" ", 1)[1] if len(message.command) > 1 else None

# ================= 🌟 MAIN MENU =================
@app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start_cmd(client, message):
    text = (
        "👋 **Welcome to Lucifer Master Bot V3.0!** 🚀\n\n"
        "**📚 LIBRARY COMMANDS (Save Permanent):**\n"
        "├ `/library` - View saved channels\n"
        "├ `/addsource` - Save a Source (ID - Name)\n"
        "├ `/addmovie` - Save a Movie Dest\n"
        "└ `/addseries` - Save a Series Dest\n\n"
        "**🎯 ACTIVE TASK COMMANDS (Build Task):**\n"
        "├ `/task` - View current active task\n"
        "├ `/set_source` - Set Target Source\n"
        "├ `/task_movie` - Add Movie Target\n"
        "├ `/task_series` - Add Series Target\n"
        "└ `/cleartask` - Clear current task\n\n"
        "**🎛️ DASHBOARD & CONFIG:**\n"
        "├ `/config` - System Status & X-Ray\n"
        "└ `/engine` - Open Live Control Panel ⚡️"
    )
    await message.reply_text(text)

# ================= ⚙️ V3.0 SYSTEM CONFIG =================
@app.on_message(filters.command("config") & filters.user(ADMIN_ID))
async def config_cmd(client, message):
    conf = await db.get_config()
    task = await db.get_active_task()
    
    text = "⚙️ **SYSTEM CONFIGURATION (V3.0)**\n\n"
    text += f"🤖 **Worker Bots Available:** {len(conf.get('tokens', []))}\n\n"
    
    text += "📚 **LIBRARY DATABASE:**\n"
    text += f"├ Sources Saved: {len(conf.get('sources', []))}\n"
    text += f"├ Movie Targets: {len(conf.get('movie_dests', []))}\n"
    text += f"└ Series Targets: {len(conf.get('series_dests', []))}\n\n"
    
    text += "🎯 **CURRENT ACTIVE TASK:**\n"
    text += f"├ Active Source: {task.get('source') or 'None'}\n"
    text += f"├ Movie Targets: {len(task.get('movie_dests', []))}\n"
    text += f"└ Series Targets: {len(task.get('series_dests', []))}\n"
    
    await message.reply_text(text)

# ================= 🤖 BOT MANAGEMENT =================
@app.on_message(filters.command("addbot") & filters.user(ADMIN_ID))
async def addbot_cmd(client, message):
    token = get_arg(message)
    if not token: return await message.reply_text("⚠️ Send token like: `/addbot 1234:ABCDE...`")
    conf = await db.get_config()
    if token not in conf["tokens"]:
        conf["tokens"].append(token)
        await db.set_config(conf)
        await message.reply_text(f"✅ Bot added! Total bots: {len(conf['tokens'])}")
    else: await message.reply_text("⚠️ Bot already exists.")

# ================= 📚 V3.0 LIBRARY COMMANDS =================
@app.on_message(filters.command("addsource") & filters.user(ADMIN_ID))
async def addsource_cmd(client, message):
    val = get_arg(message)
    if not val: return await message.reply_text("⚠️ `/addsource -100xxx - Source Name`")
    conf = await db.get_config()
    if val not in conf["sources"]:
        conf["sources"].append(val)
        await db.set_config(conf)
        await message.reply_text("✅ Source Saved in Permanent Library! 📚")

@app.on_message(filters.command("addmovie") & filters.user(ADMIN_ID))
async def addmovie_cmd(client, message):
    val = get_arg(message)
    if not val: return await message.reply_text("⚠️ `/addmovie -100xxx - Movie Channel`")
    conf = await db.get_config()
    if val not in conf["movie_dests"]:
        conf["movie_dests"].append(val)
        await db.set_config(conf)
        await message.reply_text("✅ Movie Dest Saved in Permanent Library! 📚")

@app.on_message(filters.command("addseries") & filters.user(ADMIN_ID))
async def addseries_cmd(client, message):
    val = get_arg(message)
    if not val: return await message.reply_text("⚠️ `/addseries -100xxx - Series Channel`")
    conf = await db.get_config()
    if val not in conf["series_dests"]:
        conf["series_dests"].append(val)
        await db.set_config(conf)
        await message.reply_text("✅ Series Dest Saved in Permanent Library! 📚")

@app.on_message(filters.command("library") & filters.user(ADMIN_ID))
async def library_cmd(client, message):
    conf = await db.get_config()
    text = "📚 **YOUR SAVED LIBRARY:**\n\n**Sources:**\n"
    for s in conf["sources"]: text += f"├ {s}\n"
    text += "\n**Movie Dests:**\n"
    for m in conf["movie_dests"]: text += f"├ {m}\n"
    text += "\n**Series Dests:**\n"
    for s in conf["series_dests"]: text += f"├ {s}\n"
    await message.reply_text(text)

# ================= 🎯 V3.0 ACTIVE TASK SELECTION =================
@app.on_message(filters.command("set_source") & filters.user(ADMIN_ID))
async def set_source_cmd(client, message):
    val = get_arg(message)
    if not val: return await message.reply_text("⚠️ Send ID to set as Active Source.")
    task = await db.get_active_task()
    task["source"] = val
    await db.set_active_task(task)
    await message.reply_text(f"🎯 **Active Task Source Set:**\n{val}")

@app.on_message(filters.command("task_movie") & filters.user(ADMIN_ID))
async def task_movie_cmd(client, message):
    val = get_arg(message)
    task = await db.get_active_task()
    if val not in task["movie_dests"]:
        task["movie_dests"].append(val)
        await db.set_active_task(task)
        await message.reply_text(f"🎯 Added to Task (Movie): {val}")

@app.on_message(filters.command("task_series") & filters.user(ADMIN_ID))
async def task_series_cmd(client, message):
    val = get_arg(message)
    task = await db.get_active_task()
    if val not in task["series_dests"]:
        task["series_dests"].append(val)
        await db.set_active_task(task)
        await message.reply_text(f"🎯 Added to Task (Series): {val}")

@app.on_message(filters.command("cleartask") & filters.user(ADMIN_ID))
async def cleartask_cmd(client, message):
    await db.set_active_task({"source": None, "movie_dests": [], "series_dests": []})
    await db.update_progress(1, 0, 0, 0, "Clean Slate... Build Task!", time.time()) # Wipes old Ghost Data
    await message.reply_text("🧹 Active Task Cleared & Progress Reset! Build a new task.")

@app.on_message(filters.command("task") & filters.user(ADMIN_ID))
async def show_task_cmd(client, message):
    task = await db.get_active_task()
    text = "🎯 **CURRENT ACTIVE TASK:**\n\n"
    text += f"📡 **Source:** {task['source'] or 'None'}\n\n"
    text += f"🎬 **Movie Targets:**\n"
    for m in task["movie_dests"]: text += f"├ {m}\n"
    text += f"\n📺 **Series Targets:**\n"
    for s in task["series_dests"]: text += f"├ {s}\n"
    await message.reply_text(text)

# ================= 🎛️ V3.0 ENGINE DASHBOARD & UI =================
def create_progress_bar(percentage):
    filled = int(percentage / 10)
    bar = "⬤" * filled + "○" * (10 - filled)
    return f"〘{bar}〙 {percentage:.1f}%"

def format_time(seconds):
    if seconds < 0: return "0s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0: return f"{h}h {m}m {s}s"
    elif m > 0: return f"{m}m {s}s"
    else: return f"{s}s"

async def get_dashboard_text_and_markup():
    status = await db.get_engine_status()
    prog = await db.get_progress()
    task = await db.get_active_task()
    
    if not prog or status == "STOPPED":
        text = f"🎛 **Lucifer V3.0 Engine Dashboard**\n\n🎯 **Active Source:** {task['source'] or 'None'}\nStatus: 🛑 STOPPED\nPress START to begin routing."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ START ENGINE", callback_data="cmd_start")]])
        return text, markup

    total = prog.get("total", 1)
    processed = prog.get("processed", 0)
    success = prog.get("success", 0)
    failed = prog.get("failed", 0)
    last_file = prog.get("last_file", "Scanning...")
    start_time = prog.get("start_time", time.time())
    
    percentage = (processed / total) * 100 if total > 0 else 0
    percentage = min(100.0, percentage)
    
    elapsed_time = time.time() - start_time
    speed = processed / elapsed_time if elapsed_time > 0 else 0
    eta_seconds = ((total - processed) / speed) if speed > 0 else 0
    
    status_emoji = "🚀 RUNNING" if status == "RUNNING" else "⏸ PAUSED"
    
    text = (
        f"**Batch Task {status_emoji}!**\n"
        f"{create_progress_bar(percentage)}\n\n"
        f"📄 **Last File:** `{last_file}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Total:** {total}\n"
        f"🔄 **Processed:** {processed}\n"
        f"✅ **Success:** {success} | ❌ **Failed/Skipped:** {failed}\n"
        f"⚡ **Speed:** {speed:.1f} files/sec\n"
        f"⏱ **Elapsed:** {format_time(elapsed_time)} | ⏳ **ETA:** {format_time(eta_seconds)}"
    )

    if status == "RUNNING":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏸ PAUSE", callback_data="cmd_pause"),
             InlineKeyboardButton("🛑 STOP", callback_data="cmd_stop_confirm")]
        ])
    else: 
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ RESUME", callback_data="cmd_resume"),
             InlineKeyboardButton("🛑 STOP", callback_data="cmd_stop_confirm")]
        ])
    return text, markup

@app.on_message(filters.command("engine") & filters.user(ADMIN_ID))
async def show_engine(client, message):
    old_msg = await db.get_tracking_msg()
    if old_msg:
        try: await client.delete_messages(old_msg["chat_id"], old_msg["message_id"])
        except Exception: pass
            
    try: await message.delete() 
    except: pass

    text, markup = await get_dashboard_text_and_markup()
    msg = await message.reply_text(text, reply_markup=markup)
    await db.set_tracking_msg(msg.chat.id, msg.id)

# ================= 🖱️ BUTTON HANDLERS =================
@app.on_callback_query(filters.user(ADMIN_ID))
async def handle_buttons(client, query):
    data = query.data
    
    if data == "cmd_start":
        await db.update_progress(1, 0, 0, 0, "Starting New Batch...", time.time()) # Force wipes old data instantly
        await db.set_engine_status("RUNNING")
        await query.answer("Engine Started Fresh! 🚀", show_alert=True)
    elif data == "cmd_resume":
        await db.set_engine_status("RUNNING")
        await query.answer("Engine Resumed! 🚀", show_alert=True)
    elif data == "cmd_pause":
        await db.set_engine_status("PAUSED")
        await query.answer("Engine Paused! ⏸", show_alert=True)
    elif data == "cmd_stop_confirm":
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ YES, STOP", callback_data="cmd_stop_yes"),
             InlineKeyboardButton("❌ NO, GO BACK", callback_data="cmd_stop_no")]
        ])
        try: await query.edit_message_text("⚠️ **Stop Engine?**", reply_markup=markup)
        except Exception: pass
        return
    elif data == "cmd_stop_yes":
        await db.set_engine_status("STOPPED")
        await query.answer("Engine Stopped completely. 🛑", show_alert=True)
    elif data == "cmd_stop_no":
        await query.answer("Action Cancelled.", show_alert=False)

    text, markup = await get_dashboard_text_and_markup()
    try: await query.edit_message_text(text, reply_markup=markup)
    except Exception: pass 

# ================= 🔄 BACKGROUND AUTO-UPDATER =================
async def live_updater():
    while True:
        try:
            tracking = await db.get_tracking_msg()
            status = await db.get_engine_status()
            if tracking and status == "RUNNING":
                text, markup = await get_dashboard_text_and_markup()
                try:
                    await app.edit_message_text(
                        chat_id=tracking["chat_id"], 
                        message_id=tracking["message_id"], 
                        text=text, 
                        reply_markup=markup
                    )
                except Exception: pass
        except Exception: pass
        await asyncio.sleep(20) 

if __name__ == "__main__":
    print("🤖 Master Bot V3.0 (Library & Tasks) Started!")
    app.start()
    asyncio.get_event_loop().create_task(live_updater())
    import idlelib; asyncio.get_event_loop().run_forever()
