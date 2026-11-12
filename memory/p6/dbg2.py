import sys; sys.argv=['x']
exec(open('sim.py').read().split("async def main")[0])
import asyncio
async def m():
    pb,_=server.get_object(PERSON); pb=head_lock.crop_screenshot(pb)
    send, lock = head_lock.prepare(pb, True, [], [], True, [], 0.0, True)
    c=lock["canvas"]; H,W=c.shape[:2]
    res=np.array(head_lock._open_small(open(RAW,'rb').read(), max(H,W)).convert("RGB"))
    reg=head_lock._register(c,res)
    ko=pose_lock.keypoints(c); kr=pose_lock.keypoints(reg)
    for name,idx in (("Lhand",range(91,112)),("Rhand",range(112,133)),("body",[5,6,7,8,9,10,11,12,13,14])):
        idx=[i for i in idx if ko[i,2]>.3 and kr[i,2]>.3]
        d=kr[idx,:2]-ko[idx,:2]
        print(name, len(idx), "mean", d.mean(0).round(1), "max", np.hypot(*d.T).max().round(1))
asyncio.run(m())
