import time
import pprint
import json
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse,urljoin
from tinydb import TinyDB
import os
import uuid
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer('all-MiniLM-L6-v2')


pp = pprint.PrettyPrinter()
visited={}
fetched=set()
def getManifestURL(site,url):
    mainfestTag=site.find("link",attrs={"rel":"manifest"})
    if mainfestTag:
        link=mainfestTag.get("href")
        if(not link.startswith("https://")):
            link=urljoin(url,link)
        link=link.replace("www.","")
        return link
    print("❌ No mainfest tag found for",url)
    return None

def getManifestJSON(manifestURL, url):
    if(manifestURL == None):
        return None
    if(not manifestURL.startswith("https://")):
        print("❌ Invalid manifest URL",manifestURL)
        return None
    r = requests.get(manifestURL)
    try:
        jsonManifest = json.loads(r.content)
    except Exception as e:
        print("⚠️ Error getting manifest ",e,r.content[:32])
        jsonManifest=None
    if(str(jsonManifest) in fetched):
        print("🔃 Manifest already fetched",manifestURL)
        return None
    fetched.add(str(jsonManifest))
    jsonManifest["manifestURL"]=manifestURL
    return jsonManifest

def processManifest(manifest,url):
    if(manifest == None):
        return None
    
    app_data={
        "url": url,
        "views":0,
        "clicks":0,
        "reviews":[]
    }
    if("start_url" in manifest):
        if(manifest["start_url"].startswith("https://")):
            app_data["url"] = manifest["start_url"]
        else:
            app_data["url"] =  urljoin(url,manifest["start_url"]) 
    fields=["background_color",
        "categories",
        "description",
        "icons",
        "name",
        "screenshots",
        "short_name",
        "theme_color",
        "related_applications",
        "lang",
        "manifestURL"]
    must_have_fields=["name","short_name","icons"]
    for field in fields:
        if( field in manifest):
            app_data[field] = manifest[field]
    proper_manifest = True
    for field in must_have_fields:
        if field not in app_data or app_data[field] == "":
            proper_manifest = False
    if proper_manifest:
        searchString = json.dumps(list(manifest.values()))
        searchString=searchString.lower()\
        .replace('br','')\
        .replace('<',"")\
        .replace(">","")\
        .replace('\\',"")\
        .replace('\/',"")\
        .replace('{',"")\
        .replace('}',"")\
        .replace('[',"")\
        .replace(']',"")\
        .replace(',',"")\
        .replace('"',"")
        app_data["searchString"] = searchString
        app_data["encoding"]=model.encode(searchString).tolist()
        return app_data
    else:
        missing_fields = list(filter(lambda x:x not in app_data ,must_have_fields))
        print("❌ Required fields not found:",missing_fields)
        return None

def update_database(info,url):
    if(info != None):
        id=uuid.uuid4().hex
        info["added_time"]=time.time()
        info["id"]=id
        db = TinyDB('../dbs/app.json', sort_keys=True, indent=4, separators=(',', ': '))
        db.insert(info)
        print("✅ Saved ",url,"Manifest")


def addToVisited(url):
     components = urlparse(url)
     if(components.netloc in visited):
        visited[components.netloc].append(components.path)
     else:
        visited[components.netloc]=[components.path]
def isVisited(url):
    components = urlparse(url)
    if components.netloc not in visited:
        return False
    # if components.path not in visited[components.netloc]:
    #     return False
    return True
def shouldProcessManifest(url):
    components = urlparse(url)
    if components.netloc in visited:
        return False
    return True
def formatUrl(url,base):
    if(url==None):
        return None
    if(not url.startswith("https://")):
        url=urljoin(base,url)
    if(url.endswith(".pdf")):
        return None
    if(url.endswith("/")):
        url=url[:-1]
    components = urlparse(url)
    if(components.scheme == None):
        return None
    
    built_url=components.scheme+"://"+components.netloc
    if(components.path):
        built_url+=components.path
    return built_url
def crawler(url,pipeline=[]):
    print("Scraping ",url)
    try:
        r=requests.get(url,timeout=10)
    except Exception as e:
        print("Failed to fetch",e)
        return;
    if("Content-Type" not in r.headers or "text/html" not in r.headers["Content-Type"]):
        print("Invalid Content-Type")
        return
    site=BeautifulSoup(r.content,features="html5lib")
    op = site
    if shouldProcessManifest(url):
        for function in pipeline:
            try:
                op = function(op,url)
            except Exception as e:
                print("Failed to run pipeline",e)
                return;
    else:
        print("🔃 Already visited ",url)
    addToVisited(url)
    for a in site.find_all('a'):
        new_url = a.get("href")
        new_url=formatUrl(new_url,url)
        if(new_url == None):
            continue
        if(not isVisited(new_url) and new_url.startswith("https")):
            crawler(new_url,pipeline)
def reset():
   if os.path.exists("../dbs/app.json"):
    os.remove("../dbs/app.json")
   else:
    print("The file does not exist")

reset()
START="https://google.com";
crawler(START,[getManifestURL,getManifestJSON,processManifest,update_database])



