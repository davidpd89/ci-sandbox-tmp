#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, urllib.parse, urllib.request
from pathlib import Path

<<<<<<< HEAD
UA='AutoraDemo-RRSS/IG06 (+https://autorademodiaz.com)'
=======
UA='DavidPorto-RRSS/IG06 (+https://davidportodiaz.com)'
>>>>>>> origin/research/public-reuse-parent
COMMONS_API='https://commons.wikimedia.org/w/api.php'
MET_API='https://collectionapi.metmuseum.org/public/collection/v1/objects/{id}'

def get_json(url:str)->dict:
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=45) as r: return json.load(r)

def download(url:str,dest:Path)->None:
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=90) as r: dest.write_bytes(r.read())

def commons(src:dict)->tuple[str,dict]:
    q=urllib.parse.urlencode({'action':'query','format':'json','prop':'imageinfo','iiprop':'url|extmetadata','titles':'File:'+src['filename']})
    data=get_json(COMMONS_API+'?'+q); page=next(iter(data['query']['pages'].values())); ii=page['imageinfo'][0]; meta=ii.get('extmetadata',{})
    license_name=(meta.get('LicenseShortName') or {}).get('value','')
    expected=src['expected_license'].casefold()
    if expected not in license_name.casefold() and not (expected=='public domain' and ('public domain' in license_name.casefold() or license_name.casefold().startswith('pd'))):
        raise SystemExit(f"IG06_ASSET_BLOCKED: {src['filename']} licencia={license_name!r}, esperada={src['expected_license']!r}")
    return ii['url'], {'provider':'Wikimedia Commons','license':license_name,'page_url':src['page_url'],'direct_url':ii['url']}

def met(src:dict)->tuple[str,dict]:
    meta=get_json(MET_API.format(id=src['object_id']))
    if meta.get('objectID')!=src['object_id'] or meta.get('isPublicDomain') is not True or (meta.get('title') or '').strip()!=src['expected_title']:
        raise SystemExit(f"IG06_ASSET_BLOCKED: Met {src['object_id']} ya no coincide con manifest")
    if not meta.get('primaryImage'): raise SystemExit('IG06_ASSET_BLOCKED: Met sin primaryImage')
    return meta['primaryImage'], {'provider':'The Metropolitan Museum of Art','license':'Public Domain','page_url':src['page_url'],'direct_url':meta['primaryImage'],'object_id':src['object_id']}

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('manifest',type=Path); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    data=json.loads(a.manifest.read_text(encoding='utf-8')); a.out.mkdir(parents=True,exist_ok=True); records=[]
    for ep in data['episodes']:
        src=ep['source']; url,meta=(commons(src) if src['type']=='commons' else met(src))
        dest=a.out/f"{ep['id']}_source.jpg"; download(url,dest)
        side={'episode':ep['id'],'source':meta,'asset':dest.name}; (a.out/f"{ep['id']}_source.json").write_text(json.dumps(side,ensure_ascii=False,indent=2),encoding='utf-8'); records.append(side)
        print(f"SOURCE_OK {ep['id']} {meta['provider']} {meta['license']}")
    (a.out/'source_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
