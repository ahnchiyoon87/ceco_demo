"""Isolated Mosquitto bridge regression: restart after persistent sessions expire.

Uses private test containers and bind-mounted test data, no CECO volumes or accounts.
Runs old/global-expiry and MQTT-v5-only expiry configurations side by side.
"""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments' / 'BOOTH-20261013' / 'bridge-probe-5s'
IMAGE = 'eclipse-mosquitto:2.1.2-alpine'
NETWORK = 'ceco-booth-bridge-probe'


def docker(*args, check=True):
    r = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode:
        raise RuntimeError(r.stderr)
    return r


def received(name, label):
    topic = 'probe/' + label
    subscriber = subprocess.Popen(['docker','exec',name+'-dst','mosquitto_sub','-h','localhost','-t',topic,'-C','1','-W','6'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    time.sleep(1)
    docker('exec',name+'-src','mosquitto_pub','-h','localhost','-t',topic,'-m',label,'-q','1')
    stdout, stderr = subscriber.communicate(timeout=12)
    return {'received':stdout.strip()==label,'stdout':stdout.strip(),'stderr':stderr.strip()}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    names=[]
    results={}
    docker('network','create',NETWORK)
    try:
        for key in ('old','fixed'):
            name='ceco-booth-'+key
            names.extend([name+'-src',name+'-dst'])
            folder=OUT/key
            folder.mkdir(exist_ok=True)
            (folder/'data').mkdir(exist_ok=True)
            (folder/'dst.conf').write_text('listener 1883\nallow_anonymous true\nlog_dest stdout\n',encoding='utf-8')
            conf='listener 1883\nallow_anonymous true\npersistence true\npersistence_location /data/\nautosave_interval 1\nlog_dest stdout\nlog_type all\n'
            if key=='old':
                conf+='persistent_client_expiration 5s\n'
            conf+=f'connection probe\naddress {name}-dst:1883\nbridge_protocol_version mqttv50\nbridge_session_expiry_interval 60\nremote_clientid probe-remote\nlocal_clientid probe-local\ncleansession false\nrestart_timeout 1\ntopic probe/# out 1\n'
            (folder/'src.conf').write_text(conf,encoding='utf-8')
            common=['run','-d','--network',NETWORK,'--user','root']
            docker(*common,'--name',name+'-dst','-v',str(folder/'dst.conf')+':/cfg.conf:ro',IMAGE,'mosquitto','-c','/cfg.conf')
            docker(*common,'--name',name+'-src','-v',str(folder/'src.conf')+':/cfg.conf:ro','-v',str(folder/'data')+':/data',IMAGE,'mosquitto','-c','/cfg.conf')
        time.sleep(3)
        for key in ('old','fixed'):
            results[key]={'before':received('ceco-booth-'+key,'before-'+key)}
            assert results[key]['before']['received'], results
        docker('stop','ceco-booth-old-src','ceco-booth-fixed-src')
        print('Both bridges stopped; waiting 8 seconds for saved sessions to expire.',flush=True)
        time.sleep(8)
        docker('start','ceco-booth-old-src','ceco-booth-fixed-src')
        time.sleep(3)
        for key in ('old','fixed'):
            results[key]['after']=received('ceco-booth-'+key,'after-'+key)
            log=docker('logs','ceco-booth-'+key+'-src')
            (OUT/(key+'.log')).write_text(log.stdout+log.stderr,encoding='utf-8')
        (OUT/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(json.dumps(results,indent=2),flush=True)
        results['cold_start_failure_reproduced'] = not results['old']['after']['received']
        (OUT/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        assert results['fixed']['after']['received'], 'MQTT v5-only expiry did not survive restart'
    finally:
        for name in names:
            docker('rm','-f',name,check=False)
        docker('network','rm',NETWORK,check=False)


if __name__=='__main__':
    main()
