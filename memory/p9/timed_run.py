import asyncio, time, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import server

async def m():
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    req = server.GridOutfitRequest(person_path="vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg", preserve_pose=True, items=[
        server.GridItem(slot="top", image_path="vfit/garment/user_389c87aaadc6/cdaae92f195a4ebba0a229ccf69fe285.jpg"),
        server.GridItem(slot="bottom", image_path="vfit/garment/user_389c87aaadc6/808c6955971a4f58b4ab9d8471406ca7.jpg"),
        server.GridItem(slot="shoes", image_path="vfit/garment/user_389c87aaadc6/73558e38ac314040aa95518048b814e5.jpg")])
    t = time.monotonic()
    r = await server._outfit_generate_from_uploads(req, user)
    print("RESULT", r.get("id") if isinstance(r, dict) else r, "TOTAL_WALL", round(time.monotonic() - t, 1), flush=True)

asyncio.run(m())
