import sys,asyncio,io;sys.path.insert(0,'/app/backend')
from dotenv import load_dotenv;load_dotenv('/app/backend/.env')
import server,tryon_quality,head_lock as h
from PIL import Image
R='/app/memory/raw/'
P='vfit/person/user_389c87aaadc6/f2c602d6d02c43c8a2c81c8fab2e52dc.jpg'
async def fake_call(system,prompt,contents,tag,aspect):
    return open(R+('surgical_raw_outfit-user_389c87aaadc6_ed8052.png' if tag.startswith('outfit') else 'legs_raw_7f7ff9.png'),'rb').read()
tryon_quality._image_call=fake_call
saved={}
server.put_object=lambda p,d,ct: saved.__setitem__('img',d) or {"path":p}
async def main():
    u=await server.db.users.find_one({"email":"andremo2014@gmail.com"},{"_id":0})
    user=server.User(**u)
    o=await server.db.outfits.find_one({"id":"582858b4-8dce-4663-a876-a49da25017f6"},{"_id":0,"items":1})
    items=[{"slot":i.get("slot"),"image_path":i["image_path"],"category":i.get("category"),"name":i.get("name")} for i in o["items"]]
    await server._multipass_outfit(user,P,items,server._GRID_LAYER_TEXT,server._owner_extra(user,True))
    im=Image.open(io.BytesIO(saved['img'])).convert('RGB');im.save(R+'sim3.jpg')
    im.crop((150,650,600,1000)).resize((900,700)).save(R+'sim3_zoom.jpg');print('ok')
asyncio.run(main())
