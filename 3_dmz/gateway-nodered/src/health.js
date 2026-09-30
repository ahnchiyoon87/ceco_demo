msg.payload = { status: 'ok', broker: !!flow.get('connected') };
return msg;
