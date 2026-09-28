from backend.src.modules.agent_session.service import _init_model
import re,os
try:
    reply=_init_model('answer',request_timeout=25,max_retries=0).invoke('Reply only OK.')
    print('MODEL_CALL_OK', bool(reply.content))
except Exception as exc:
    message=str(exc)
    for key,value in os.environ.items():
        if any(x in key for x in ['KEY','TOKEN','PASSWORD','SECRET']) and len(value)>5:
            message=message.replace(value,'[REDACTED]')
    message=re.sub(r'https?://[^\s\"\x27]+','[URL]',message)
    print(type(exc).__name__,message[:1400])
