import asyncio, time, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import server

async def m():
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    req = server.GridOutfitRequest(person_path="vfit/person/user_389c87aaadc6/d7170eb97b634fd2a4e0b8feee19ff26.png", preserve_pose=True, items=[
        server.GridItem(slot="top", image_path="vfit/garment/user_389c87aaadc6/9cedf2f1f4bc48fda14f1f88403a4c0f.jpg"),
        server.GridItem(slot="bottom", image_path="vfit/garment/user_389c87aaadc6/56db990069d04874af1dfc995c120e80.jpg"),
        server.GridItem(slot="shoes", image_path="vfit/garment/user_389c87aaadc6/b60915c2425e415ea8691e49c101fd52.jpg")])
    t = time.monotonic()
    r = await server._outfit_generate_from_uploads(req, user)
    print("RESULT", r.get("id") if isinstance(r, dict) else r, "TOTAL_WALL", round(time.monotonic() - t, 1), flush=True)

asyncio.run(m())
