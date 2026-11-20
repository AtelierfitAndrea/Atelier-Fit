import asyncio, time, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import server
server.TRYON_VARIANTS = 1

async def m():
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    req = server.GridOutfitRequest(person_path="vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg", preserve_pose=True, items=[
        server.GridItem(slot="top", image_path="vfit/garment/user_389c87aaadc6/b01e214cba244720b62f9740b4f8ebe2.jpg"),
        server.GridItem(slot="bottom", image_path="vfit/garment/user_389c87aaadc6/5dc7e1bf3e2d40a99c57d7b046cfaa80.jpg"),
        server.GridItem(slot="shoes", image_path="vfit/garment/user_389c87aaadc6/e914b0160b164755a105de58ec6aa660.jpg")])
    t = time.monotonic()
    r = await server._outfit_generate_from_uploads(req, user)
    print("RESULT", r.get("id") if isinstance(r, dict) else r, "TOTAL_WALL", round(time.monotonic() - t, 1), flush=True)

asyncio.run(m())
