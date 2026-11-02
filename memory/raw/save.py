import sys,io,uuid;sys.path.insert(0,'/app/backend')
from dotenv import load_dotenv;load_dotenv('/app/backend/.env')
import server,os
from pymongo import MongoClient
from PIL import Image
buf=io.BytesIO();Image.open('/app/memory/raw/sim3.jpg').save(buf,'JPEG',quality=95)
p=f"vfit/outfit/user_389c87aaadc6/{uuid.uuid4().hex}.jpg";server.put_object(p,buf.getvalue(),"image/jpeg")
db=MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
print(db.outfits.update_one({"id":"582858b4-8dce-4663-a876-a49da25017f6"},{"$set":{"result_path":p}}).modified_count)
