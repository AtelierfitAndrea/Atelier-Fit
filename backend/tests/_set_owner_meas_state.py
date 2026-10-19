# Helper: set owner measurement state for UI tests. usage: python _set_owner_meas_state.py incomplete|complete
import sys, json
from datetime import datetime, timezone
from pymongo import MongoClient
from cryptography.fernet import Fernet
from dotenv import dotenv_values

ENV = dotenv_values("/app/backend/.env")
db = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
F = Fernet(ENV["DATA_ENCRYPTION_KEY"].encode())
UID = "user_389c87aaadc6"
data = {"height_cm": 172, "chest_cm": 94, "waist_cm": 78, "hips_cm": 98, "shoulder_cm": 44, "inseam_cm": 80, "gender": "female"}
if sys.argv[1] == "incomplete":
    data["method"] = "auto_photo"
else:
    data["method"] = "tape"
db.measurements.update_one({"user_id": UID}, {"$set": {"enc": F.encrypt(json.dumps(data).encode()).decode(),
                                                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
print("ok", sys.argv[1])
