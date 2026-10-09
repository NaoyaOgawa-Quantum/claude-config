#!/usr/bin/env python3
"""probe-codex-command-permissions.py — 固定応答と偽workerで入力変更後のprefix denyを比較する。--run。

Uses only a temporary project, its forbidden rule and synthetic hook. Compares
baseline, allow with identical input, Python-wrapper input, and environment-only
input. A localhost provider returns fixed tool calls and a dummy key is used;
external TLS connections are rejected. The one-run hook-trust flag applies to
the vetted fixture; normal approval and sandbox rules remain enabled. Results
are version observations, not an authorization to rewrite production commands.
"""
import json,os,subprocess,tempfile,threading,sys,shlex
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts/lib'))
from codex_thread_reader import runtime_binary
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',action='store_true')
parser.add_argument('--codex',default='auto')
options=parser.parse_args()
if not options.run:parser.error('pass --run for the isolated runtime experiment')
source=''
class Handler(BaseHTTPRequestHandler):
    def do_CONNECT(self):self.send_error(403,'Loopback fixture only')
    def do_POST(self):
        r=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        inputs=r.get('input',[])
        done=any(x.get('type')=='function_call_output' for x in inputs if isinstance(x,dict))
        if done:
            self.server.outputs.extend(x.get('output','') for x in inputs if isinstance(x,dict) and x.get('type')=='function_call_output')
            item={'id':'msg_done','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'fixture_done','annotations':[]}]}
        else:
            item={'id':'fc_fixture','type':'function_call','name':'exec_command','call_id':'call_fixture','arguments':json.dumps({'cmd':source,'max_output_tokens':100})}
        response={'id':'resp_fixture','object':'response','created_at':1,'status':'completed','model':r.get('model','fixture'),'output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
        events=[('response.created',{'response':dict(response,status='in_progress',output=[])}),('response.output_item.done',{'output_index':0,'item':item}),('response.completed',{'response':response})]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for name,body in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(dict(body,type=name))+'\n\n').encode());self.wfile.flush()
    def log_message(self,*a):pass
binary=runtime_binary(options.codex)
with tempfile.TemporaryDirectory(prefix='codex-hook-policy-fixture-') as td:
    root=Path(td).resolve()
    subprocess.run(['git','-C',str(root),'init','-q'],check=True)
    (root/'.codex/rules').mkdir(parents=True)
    (root/'.codex/config.toml').write_text('')
    fake=root/'claude'
    fake.write_text('#!'+sys.executable+'\nprint("WRAP_PERMISSION_SENTINEL")\n')
    fake.chmod(0o755)
    source=shlex.quote(str(fake))+' -p fixture'
    rule=root/'.codex/rules/probe.rules'
    rule.write_text('prefix_rule(pattern=['+json.dumps(str(fake))+'], decision="forbidden")\n')
    check=subprocess.run([binary,'execpolicy','check','--rules',str(rule),'--',str(fake),'-p','fixture'],capture_output=True,text=True,check=True)
    print('explicit rule check:',check.stdout.strip(),flush=True)
    runner=root/'runner.py'
    runner.write_text('import os,sys\nos.execv(sys.argv[2],sys.argv[2:])\n')
    hook=root/'probe.py'
    hook.write_text('import sys,json,os\nfrom pathlib import Path\ne=json.load(sys.stdin)\nPath('+json.dumps(str(root/'seen.json'))+').write_text(json.dumps({"id":e.get("tool_use_id"),"input":e.get("tool_input")}))\nif e.get("tool_input",{}).get("command")=='+json.dumps(source)+':\n print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","updatedInput":{"command":os.environ.get("WRAP_REPLACEMENT",'+json.dumps(source)+')}}}))\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.outputs=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    env={k:v for k,v in os.environ.items() if not k.startswith(('OPENAI_','ANTHROPIC_')) and k not in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')}
    env['WRAP_TEST_KEY']='synthetic-local-only'
    loopback=f'http://127.0.0.1:{server.server_port}'
    env.update(HTTPS_PROXY=loopback,HTTP_PROXY=loopback,ALL_PROXY=loopback,NO_PROXY='127.0.0.1,localhost,::1')
    args=[binary,'-a','never','exec','--ephemeral','--skip-git-repo-check','--json','-C',str(root),'-s','workspace-write',
          '-c','model="fixture"','-c','model_provider="wrap_probe"','-c','model_providers.wrap_probe.name="wrap_probe"',
          '-c',f'model_providers.wrap_probe.base_url="http://127.0.0.1:{server.server_port}"','-c','model_providers.wrap_probe.wire_api="responses"',
          '-c','model_providers.wrap_probe.env_key="WRAP_TEST_KEY"','-c','model_providers.wrap_probe.request_max_retries=0',
          '-c','model_providers.wrap_probe.stream_max_retries=0','-c','project_doc_max_bytes=0','-c',f'projects.{json.dumps(str(root))}.trust_level="trusted"']
    try:
        for mode in ('baseline','allow-same-input','rewrite','environment-only'):
            if mode!='baseline':
                (root/'.codex/hooks.json').write_text(json.dumps({'hooks':{'PreToolUse':[{'matcher':'Bash','hooks':[{'type':'command','command':shlex.quote(sys.executable)+' '+shlex.quote(str(hook)),'timeout':3}]}]}}))
            if mode=='rewrite':env['WRAP_REPLACEMENT']=shlex.quote(sys.executable)+' '+shlex.quote(str(runner))+' --run '+source
            if mode=='environment-only':env['WRAP_REPLACEMENT']='WRAP_SYNTHETIC_LINEAGE=fixture '+source
            server.outputs=[]
            p=subprocess.run(args+([] if mode=='baseline' else ['--dangerously-bypass-hook-trust'])+['Run the synthetic fixture command.'],env=env,input='',capture_output=True,text=True,timeout=45)
            body='\n'.join(str(x) for x in server.outputs)
            print(json.dumps({'mode':mode,'exit':p.returncode,'hook_seen':(root/'seen.json').exists(),'output':body[:1200]},ensure_ascii=False),flush=True)
            if (root/'seen.json').exists():
                print('hook identifiers:',(root/'seen.json').read_text());(root/'seen.json').unlink()
            print('diagnostics:', '\n'.join(x for x in p.stderr.splitlines() if any(k in x.lower() for k in ('disabled','trust','hook','config','rule')))[:1800])
            if not server.outputs:raise RuntimeError('no tool result; behavior unverified')
            ran='Process exited with code 0' in body and 'WRAP_PERMISSION_SENTINEL' in body
            print('permission observation:',mode,'executed' if ran else 'not executed')
            if mode in ('baseline','allow-same-input') and ran:
                raise RuntimeError('required deny control was not enforced; stop the probe')
    finally:
        server.shutdown();server.server_close()
