from flask import Flask, request,abort
from tinydb import TinyDB, Query
from sentence_transformers import SentenceTransformer, util
import uuid
import datetime
from urllib.parse import urljoin

app = Flask(__name__)
model = SentenceTransformer('all-MiniLM-L6-v2')

@app.route("/app", methods=['GET'])
def getAppDetails():
    args = request.args
    App = Query()
    db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
    data=db.get(App["id"] == args["id"])
    if data is not None:
        db.update({"views":data["views"]+1},App["id"]==args["id"])
        data.pop("encoding")
        data.pop("searchString")
        return data
    return abort(404)

@app.route("/click", methods=['GET'])
def clickApp():
    args = request.args
    App = Query()
    db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
    data=db.get(App["id"] == args["id"])
    if data is not None:
        db.update({"clicks":data["clicks"]+1},App["id"]==args["id"])
        data.pop("encoding")
        data.pop("searchString")
        return data
    return abort(404)

@app.route("/search", methods=['GET'])
def searchApps():
    db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
    results=db.all()
    query = request.args["query"]
    query_embedding = model.encode(query)
    result_embeddings = list(map(lambda x:x["encoding"],results))
    cos_sim = util.cos_sim(query_embedding, result_embeddings).tolist()[0]
    viewable_results=[]
    for i,result in enumerate(results):
        stars=2.5
        for review in result["reviews"]:
            stars+=review["stars"]
        stars=stars/(len(result["reviews"])+1)
        image=result["icons"][0]["src"]
        if(not image.startswith("https://")):
            if(image.startswith("/")):
               image=image[1:]
            image=urljoin(result["url"],image)
        viewable_results.append({
            "name": result["short_name"] if "short_name" in result else result["name"],
            "image": image,
            "stars": stars,
            "id": result["id"],
            "popularity":result["views"],
            "usefulness":result["clicks"]/(1 if result["views"] == 0 else result["views"]),
            "similarity": cos_sim[i],
        })
    viewable_results.sort(key=lambda x:x["similarity"],reverse=True)
    return viewable_results

@app.route("/apps", methods=['GET'])
def getApps():
    if("sortType" in request.args):
        sortType=request.args["sortType"]
    else:
        sortType="popularity"

    db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
    results=db.all()
    viewable_results=[]
    for result in results:
        stars=2.5
        for review in result["reviews"]:
            stars+=review["stars"]
        stars=stars/(len(result["reviews"])+1)
        image=result["icons"][0]["src"]
        if(not image.startswith("https://")):
            if(image.startswith("/")):
               image=image[1:]
            image=urljoin(result["url"],image)
        viewable_results.append({
            "name": result["short_name"] if "short_name" in result else result["name"],
            "image": image,
            "stars": stars,
            "id": result["id"],
            "popularity":result["views"],
            "usefulness":result["clicks"]/(1 if result["views"] == 0 else result["views"]),
            "addedTime":result["added_time"]
        })
    viewable_results.sort(key=lambda x: x[sortType],reverse=True)
    return {
        "results":viewable_results
    }


@app.route("/status", methods=['GET'])
def getStatus():
    db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
    results=db.all()
    results.sort(key=lambda x: x["added_time"],reverse=True);
    start_time = results[-1]["added_time"]
    rangeHeat=results[0]["added_time"]-results[-1]["added_time"]
    page= "You have scraped total of "+str(len(results))+" pages:<br><br><ol>"
    for result in results:
        name = result["short_name"] if "short_name" in result else result["name"]
        heat = (result["added_time"]-start_time) / rangeHeat
        page+="<li> <span class='space_box' style='background-color:rgba(255,0,0,"+str(heat)+")'>"+result["short_name"]+" : "+result["manifestURL"]+"</span></li>"
    page+="""</ol>
      <script>
        setTimeout(()=>{
        window.location.href = window.location.href
        },5000)
    </script>
    """
    return page


@app.route("/signIn", methods=['POST'])
def signInUser():
    data = request.get_json()
    email=data["email"]
    password=data["password"]
    db = TinyDB('../dbs/users.json', sort_keys=True, indent=4, separators=(',', ': '))
    User = Query()
    account=db.search(User.email == email, User.password == password)
    if(account == None):
        return abort(401)
    else:
        token = uuid.uuid4().hex
        tokenDB = TinyDB('../dbs/tokens.json')
        tokenDB.insert({
            "email":email,
            "token":token,
            "expires_at":datetime.time() + datetime.timedelta(minutes=30)
        })
        return {
            "name":account["name"],
            "email":account["email"],
            "token":token
        }
    

@app.route("/signUp", methods=['POST'])
def createAccount():
    data = request.get_json()
    email=data["email"]
    password=data["password"]
    name=data["name"]
    db = TinyDB('../dbs/users.json', sort_keys=True, indent=4, separators=(',', ': '))
    User = Query()
    account=db.search(User.email == email, User.password == password)
    if(account == None):
        new_account = {
            "name":name,
            "email":email,
            "password":password,
        }
        db.insert(new_account)
        token = uuid.uuid4().hex
        tokenDB = TinyDB('../dbs/tokens.json')
        tokenDB.insert({
            "email":email,
            "token":token,
            "expires_at":datetime.time() + datetime.timedelta(minutes=30)
        })
        return {
            "name":account["name"],
            "email":account["email"],
            "token":token
        }
    else:
        return abort(409)
   

if __name__ == '__main__':
    app.run(host="localhost", port=8000, debug=True)