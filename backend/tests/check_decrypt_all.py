# Verifies every encrypted record in Mongo decrypts with the DATA_ENCRYPTION_KEY loaded from .env (no data loss)
import os, asyncio
from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
key = os.environ["DATA_ENCRYPTION_KEY"]
print("key len", len(key), "starts with dash:", key.startswith("-"), "has quotes:", '"' in key)
f = Fernet(key.encode())


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for coll, field in (("measurements", "enc"), ("weight_history", "weight_enc")):
        ok = bad = 0
        async for d in db[coll].find({field: {"$exists": True}}):
            try:
                f.decrypt(d[field].encode()); ok += 1
            except InvalidToken:
                bad += 1
        plain = await db[coll].count_documents({"weight_kg": {"$exists": True}} if coll == "weight_history" else {"chest_cm": {"$exists": True}})
        print(coll, "ok", ok, "bad", bad, "plaintext_docs", plain)

asyncio.run(main())
