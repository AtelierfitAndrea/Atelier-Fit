import sys, asyncio, os, logging
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
logging.basicConfig(level=logging.INFO)
import server, tryon_quality

# FREE re-run: the image model is replaced by the saved raws (pass 1, then legs pass). Set GEN=1 to allow real generations.
RAWS = [open(p, "rb").read() for p in sys.argv[1].split(",")] if len(sys.argv) > 1 and sys.argv[1] else []
real = tryon_quality._image_call
calls = {"n": 0}


async def fake(system, prompt, contents, tag, aspect):
    i = calls["n"]; calls["n"] += 1
    if i < len(RAWS):
        print("FAKE CALL", i, tag)
        return RAWS[i]
    if os.environ.get("GEN") == "1" and calls.setdefault("real", 0) < 3:
        calls["real"] += 1
        print("REAL CALL", i, tag)
        b = await real(system, prompt, contents, tag, aspect)
        open(f"/app/memory/p7/gen_{i}_{tag[:6]}.png", "wb").write(b)
        calls["last"] = b
        return b
    print("EXTRA CALL", i, tag, "-> reusing last raw")
    return calls.get("last") or RAWS[-1]
tryon_quality._image_call = fake


async def main():
    doc = await server.db.outfits.find_one({"id": "6223a9a6-016a-4d2f-a2b1-20ace2d9b347"}, {"_id": 0})
    u = await server.db.users.find_one({"user_id": "user_389c87aaadc6"}, {"_id": 0})
    user = server.User(**u)
    items = []
    for it in doc["items"]:
        cat = server._GRID_SLOTS[it["slot"]][0]
        items.append({"slot": it["slot"], "image_path": it["image_path"], "category": cat, "name": it.get("name"), "brand": None})
    _, path = await server._compose_outfit(user, doc["person_path"], items, server._GRID_LAYER_TEXT, server._owner_extra(user, True))
    data, _ = server.get_object(path)
    open(sys.argv[2], "wb").write(data)
    print("RESULT", path, "calls", calls["n"])

asyncio.run(main())
