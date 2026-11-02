exec(open('/app/memory/raw/sim3.py').read().split('async def main')[0])
import numpy as np
orig_pc=h._pose_composite
cap={}
def pc(canvas,res,face,pads=(0,0),freeze=(),arms=None):
    out,f=orig_pc(canvas,res,face,pads,freeze,arms)
    if face is None: cap.update(crop=canvas.copy(),reg=res.copy(),out=out.copy())
    return out,f
h._pose_composite=pc
server.head_lock._pose_composite=pc
exec('async def main'+open('/app/memory/raw/sim3.py').read().split('async def main')[1].replace("asyncio.run(main())",""))
asyncio.run(main())
y0=586
def z(a): return a[830-y0-60:830-y0+40, 200:420]
fin=np.array(Image.open(R+'sim3.jpg'))[830-60:830+40,200:420]
row=np.vstack([z(cap['crop']),z(cap['reg']),z(cap['out']),fin])
Image.fromarray(row).resize((440,800)).save(R+'dbg4.jpg');print('ok2')
