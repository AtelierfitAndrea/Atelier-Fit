# Manual probe (not pytest): run _render_single in-process for a pose try-on, saving every raw model output to /tmp/raw_<n>.png for offline align/composite analysis. Usage: python pose_raw_probe.py <person_path> <garment_path> [category]
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO, format="  %(name)s %(message)s")
import server  # noqa: E402
import tryon_quality  # noqa: E402

orig = tryon_quality._image_call
n = [0]


async def spy(system, prompt, contents, tag, aspect):
    raw = await orig(system, prompt, contents, tag, aspect)
    n[0] += 1
    open(f"/tmp/raw_{n[0]}.png", "wb").write(raw)
    print("RAW saved", n[0], tag, aspect, len(raw), flush=True)
    return raw

tryon_quality._image_call = spy


async def go():
    try:
        p = await server._render_single("user_389c87aaadc6", sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "top", "TEST_probe", {}, server.POSE_RULE)
        print("RESULT", p)
    except Exception as e:
        print("ERR", getattr(e, "status_code", None), getattr(e, "detail", e))

asyncio.run(go())
