import sys,asyncio,io,os,uuid;sys.path.insert(0,'/app/backend')
from dotenv import load_dotenv;load_dotenv('/app/backend/.env')
import server,tryon_quality
from PIL import Image
R='/app/memory/raw/'
OID,P1,LEGS=sys.argv[1],sys.argv[2],sys.argv[3]
async def fake_call(system,prompt,contents,tag,aspect):
    return open(R+(P1 if tag.startswith('outfit') else LEGS),'rb').read()
tryon_quality._image_call=fake_call
real_put=server.put_object
saved={}
server.put_object=lambda p,d,ct: saved.__setitem__('img',d) or {"path":p}
async def main():
    u=await server.db.users.find_one({"email":"andremo2014@gmail.com"},{"_id":0});user=server.User(**u)
    o=await server.db.outfits.find_one({"id":OID},{"_id":0})
    items=[{"slot":i.get("slot"),"image_path":i["image_path"],"category":i.get("category"),"name":i.get("name")} for i in o["items"]]
    await server._multipass_outfit(user,o["person_path"],items,server._GRID_LAYER_TEXT,server._owner_extra(user,True))
    p=f"vfit/outfit/{user.user_id}/{uuid.uuid4().hex}.jpg";real_put(p,saved['img'],"image/jpeg")
    await server.db.outfits.update_one({"id":OID},{"$set":{"result_path":p}})
    await server.db.book_outfits_my_atelier.update_many({"result_path":o["result_path"]},{"$set":{"result_path":p}})
    im=Image.open(io.BytesIO(saved['img']));print('ok',im.size,p);im.thumbnail((500,900));im.save(R+f'rm_{OID[:6]}.jpg')
asyncio.run(main())
