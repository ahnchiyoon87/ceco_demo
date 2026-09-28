import json,subprocess,urllib.request,urllib.error,time
from pathlib import Path
base='https://knu-litellm-h4ifvih7fq-du.a.run.app'
gcloud=r'C:\Users\roede\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
key=subprocess.run([gcloud,'secrets','versions','access','1','--secret=knu-litellm-master-key','--project=project-f49d373f-f76d-47a1-bdb'],capture_output=True,text=True,check=True).stdout.strip()
def api(path,body=None,method=None):
 req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
models=api('/model/info')['data']
m=next(x for x in models if x['model_name']=='coding')
assert m['litellm_params']['model']=='openai/gpt-6-luna'
mid=m['model_info']['id']
prior=m['litellm_params'].get('extra_body')
new={**(prior or {}),'reasoning_effort':'none'}
api('/model/'+mid+'/update',{'litellm_params':{'extra_body':new}},'PATCH')
read=next(x for x in api('/model/info')['data'] if x['model_info']['id']==mid)
assert read['litellm_params']['extra_body']==new
payload={'model':'coding','reasoning_effort':'medium','messages':[{'role':'user','content':'Call check_status with no arguments.'}],'tools':[{'type':'function','function':{'name':'check_status','description':'Read a simulated status for connectivity verification.','parameters':{'type':'object','properties':{}}}}],'tool_choice':{'type':'function','function':{'name':'check_status'}}}
report={'alias':'coding','model':'openai/gpt-6-luna','model_id':mid,'previous_extra_body':prior,'extra_body':new,'client_reasoning_effort':'medium'}
try:
 result=api('/v1/chat/completions',payload)
 calls=result['choices'][0]['message'].get('tool_calls',[])
 assert calls and calls[0]['function']['name']=='check_status'
 report.update(status='FUNCTION_CALL_VERIFIED',tool_name=calls[0]['function']['name'])
except Exception as e:
 api('/model/'+mid+'/update',{'litellm_params':{'extra_body':prior or {}}},'PATCH')
 report.update(status='ROLLED_BACK',error_type=type(e).__name__)
 if isinstance(e,urllib.error.HTTPError):
  body=json.loads(e.read())
  message=body.get('error',{}).get('message','')
  report['error']=message.replace(key,'[REDACTED]')[:800]
Path('docs/ai-work/uiux-20260928/gcp-litellm-fix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
