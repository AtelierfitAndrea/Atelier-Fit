import asyncio, time, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import server

async def m():
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    req = server.GridOutfitRequest(person_path="vfit/person/user_389c87aaadc6/396bf1a9bf3b443383813e9f83b8c261.png", preserve_pose=True, items=[
        server.GridItem(slot="top", image_path="vfit/garment/user_389c87aaadc6/09b0c65f035b48c08e18e24c92321f45.jpg"),
        server.GridItem(slot="bottom", image_path="vfit/garment/user_389c87aaadc6/228525b02ca345109a16cb3050db81b6.jpg"),
        server.GridItem(slot="shoes", image_path="vfit/garment/user_389c87aaadc6/f4fae4d8704a40ed88cb41d0b12ddd05.jpg")])
    t = time.monotonic()
    r = await server._outfit_generate_from_uploads(req, user)
    print("RESULT", r.get("id") if isinstance(r, dict) else r, "TOTAL_WALL", round(time.monotonic() - t, 1), flush=True)

asyncio.run(m())
