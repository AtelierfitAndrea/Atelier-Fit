import io, resource, sys, time
sys.path.insert(0, "/app/backend")
import numpy as np
from PIL import Image
import head_lock

rng = np.random.default_rng(0)
big = Image.fromarray(rng.integers(0, 255, (4000, 3000, 3), dtype=np.uint8))
buf = io.BytesIO(); big.save(buf, "JPEG", quality=92); person = buf.getvalue(); del big
g = io.BytesIO(); Image.fromarray(rng.integers(0, 255, (4000, 3000, 4), dtype=np.uint8), "RGBA").save(g, "PNG"); garment = g.getvalue()
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
t = time.time()
small_person = head_lock.downscale(person, 1536) if hasattr(head_lock, "downscale") else person
small_garment = head_lock.downscale(garment, 1024) if hasattr(head_lock, "downscale") else garment
canvas, meta = head_lock.prepare(person, True)
H, W = meta["canvas"].shape[:2]
r = io.BytesIO(); Image.fromarray(rng.integers(0, 255, (1536, 1024, 3), dtype=np.uint8)).save(r, "PNG")
out = head_lock.finalize(r.getvalue(), meta)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print("person in", Image.open(io.BytesIO(person)).size, "-> upload", Image.open(io.BytesIO(small_person)).size)
print("garment in 4000x3000 RGBA ->", Image.open(io.BytesIO(small_garment)).size, Image.open(io.BytesIO(small_garment)).mode)
print("canvas", (W, H), "output", Image.open(io.BytesIO(out)).size)
print(f"rss baseline {base:.0f}MB peak {peak:.0f}MB delta {peak-base:.0f}MB time {time.time()-t:.1f}s")
