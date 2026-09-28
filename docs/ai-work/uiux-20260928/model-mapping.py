from backend.src.modules.agent_session.service import _resolve_agent_model_profile
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,urlunsplit
import json
p=_resolve_agent_model_profile('answer')
u=urlsplit(p.base_url)
base=urlunsplit((u.scheme,u.netloc,'','',''))
for route in ['/model/info','/v1/model/info']:
 try:
  with urlopen(Request(base+route,headers={'Authorization':'Bearer '+p.api_key}),timeout=20) as r:d=json.load(r)
  for x in d.get('data',[]):
   z=x.get('litellm_params',{})
   print(json.dumps({'alias':x.get('model_name'),'model':z.get('model'),'reasoning_effort':z.get('reasoning_effort'),'allowed_openai_params':z.get('allowed_openai_params')},ensure_ascii=False))
  break
 except Exception as e: print(type(e).__name__,getattr(e,'code',None))
