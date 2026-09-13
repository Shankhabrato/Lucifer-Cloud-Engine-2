import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)
db = client["LuciferCloudEngine"]
config_col = db["config"]
copied_col = db["copied_messages"]

# ================= 📚 V3.0 CHANNEL LIBRARY =================
async def get_config():
    """Yeh tumhare saare saved channels (Library) ko store karega"""
    data = await config_col.find_one({"_id": "main_config"})
    if not data:
        data = {"tokens": [], "sources": [], "movie_dests": [], "series_dests": []}
    return data

async def set_config(data):
    await config_col.update_one({"_id": "main_config"}, {"$set": data}, upsert=True)

# ================= 🎯 V3.0 ACTIVE TASK SELECTION =================
async def get_active_task():
    """Yeh store karega ki user ne library me se kaunse channels tick (✅) kiye hain"""
    data = await config_col.find_one({"_id": "active_task"})
    if not data:
        data = {"source": None, "movie_dests": [], "series_dests": []}
    return data

async def set_active_task(data):
    await config_col.update_one({"_id": "active_task"}, {"$set": data}, upsert=True)

# ================= 🚀 V3.0 ENGINE & PROGRESS =================
async def set_engine_status(status):
    await config_col.update_one({"_id": "engine_state"}, {"$set": {"status": status}}, upsert=True)

async def get_engine_status():
    data = await config_col.find_one({"_id": "engine_state"})
    return data.get("status", "STOPPED") if data else "STOPPED"

async def update_progress(total, processed, success, failed, last_file, start_time):
    await config_col.update_one(
        {"_id": "live_progress"},
        {"$set": {
            "total": total,
            "processed": processed,
            "success": success,
            "failed": failed,
            "last_file": last_file,
            "start_time": start_time
        }},
        upsert=True
    )

async def get_progress():
    return await config_col.find_one({"_id": "live_progress"})

async def set_tracking_msg(chat_id, message_id):
    """Old dashboard ko yaad rakhne ke liye taaki baad mein delete kar sakein"""
    await config_col.update_one(
        {"_id": "tracking_msg"},
        {"$set": {"chat_id": chat_id, "message_id": message_id}},
        upsert=True
    )

async def get_tracking_msg():
    return await config_col.find_one({"_id": "tracking_msg"})

# ================= 💾 FORWARDING MEMORY =================
async def get_last_copied_msg_id(source_chat):
    doc = await copied_col.find_one({"chat_id": source_chat})
    return doc["last_msg_id"] if doc else 0

async def mark_file_copied(source_chat, msg_id):
    await copied_col.update_one(
        {"chat_id": source_chat},
        {"$set": {"last_msg_id": msg_id}},
        upsert=True
    )
