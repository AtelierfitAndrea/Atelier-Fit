exec(open('/app/memory/raw/sim4.py').read().replace("Image.fromarray(row)","Image.fromarray(row)" ))
import pose_lock as pl
o=np.array(h._open_small(h.crop_screenshot(server.get_object(P)[0]),h.PERSON_OUT_SIDE).convert('RGB'))
segs,hands=pl.arm_masks(o)
m=np.dstack([hands,hands,hands])[830-60:830+40,200:420]
Image.fromarray(np.vstack([z(cap['reg']),m])).resize((440,400)).save(R+'dbg5.jpg');print('ok3')
