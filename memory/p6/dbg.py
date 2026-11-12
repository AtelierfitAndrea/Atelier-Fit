import sys; sys.argv=['x']
exec(open('sim.py').read().split("async def main")[0])
import asyncio
async def m():
    pb,_=server.get_object(PERSON); pb=head_lock.crop_screenshot(pb)
    boxes, keep, txt, freeze = await server._lock_hands(PERSON, pb, False, True, ["dress"], True)
    send, lock = head_lock.prepare(pb, True, boxes, keep, True, freeze, 0.0, True)
    c=lock["canvas"]; res=np.array(Image.open(RAW).convert("RGB"))
    reg=head_lock._register(c,res)
    H,W=c.shape[:2]
    ys,xs=np.where(lock["seated"]["keep"]>0); y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max()
    print(H,W,y0,y1,x0,x1)
    sl=(slice(y0,y1+40),slice(x0,x1))
    k=cv2.cvtColor(lock["seated"]["keep"][sl],cv2.COLOR_GRAY2RGB)
    row=np.concatenate([c[sl],reg[sl],k],1)
    cv2.imwrite('dbg_rows.jpg',cv2.cvtColor(cv2.resize(row,None,fx=1.5,fy=1.5),cv2.COLOR_RGB2BGR))
asyncio.run(m())
