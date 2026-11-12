import sys, os, asyncio, logging
sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
logging.basicConfig(level=logging.INFO)
import server


async def main():
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    req = server.TryOnRequest(person_path="vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg",
                              garment_path="vfit/garment/user_389c87aaadc6/86a7cf903e8b40cf97ef270cfc735659.jpg",
                              garment_category="dress", preserve_pose=True)
    doc = await server._tryon_generate(req, user)
    print("RESULT", doc["id"], doc["result_path"])
    data, _ = server.get_object(doc["result_path"])
    open(sys.argv[1], "wb").write(data)

asyncio.run(main())
