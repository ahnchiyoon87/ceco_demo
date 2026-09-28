import json,urllib.request
base='https://knu-litellm-h4ifvih7fq-du.a.run.app'
with urllib.request.urlopen(base+'/openapi.json',timeout=20) as r:d=json.load(r)
for path,methods in d['paths'].items():
 if 'model' in path and 'update' in path:
  print(path,json.dumps({k:v.get('requestBody',{}) for k,v in methods.items()},ensure_ascii=False)[:1500])
for k,v in d['components']['schemas'].items():
 if k in ['UpdateDeployment','UpdateModelRequest','UpdateDeploymentModelInfo']:print(k,json.dumps(v)[:2200])
