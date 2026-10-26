import asyncio, os, sys, time, resource
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import server
from server import _render_single, _get_measurements, get_object


async def main():
    t = time.time()
    user = "user_389c87aaadc6"
    path = await _render_single(user, "vfit/avatar/user_389c87aaadc6/e2bf1a90a05440ab97ba1d73de3e7ecf.bin",
                                "vfit/garment/user_389c87aaadc6/768957e7bf1c4ccbb3cb5bf01e90e899.jpg", "dress", "Abito corsetto nero lungo",
                                await _get_measurements(user))
    data, ct = get_object(path)
    open("/tmp/render_out.jpg", "wb").write(data)
    print("path", path, ct, len(data), "secs", round(time.time() - t), "maxrss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)

asyncio.run(main())
