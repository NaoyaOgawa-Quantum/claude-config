#!/usr/bin/env python3
"""probe-codex-worker-context.py — 実CLIとlocalhost固定応答でworker側記録条項を比較する。--run。

Runs only synthetic prompts with a dummy provider key. Vetted fixture hooks use
the one-invocation hook-trust flag; normal tool permission rules remain enabled.
Checks original system/task preservation, ordinary-session and empty-input
negative controls, and bounded Claude report collection. No external inference.

--installed-codex-hooks checks the currently installed trusted Codex user hooks
without project hook definitions, a trust bypass, or a Claude invocation. It
checks UserPromptSubmit/Stop delivery; Subagent/PreToolUse dispatch is outside
this mode. External TLS calls are refused by a loopback proxy.
"""
import json,os,subprocess,tempfile,threading,sys,shlex
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',action='store_true')
parser.add_argument('--codex',default='auto')
parser.add_argument('--installed-codex-hooks',action='store_true',
                    help='check installed trusted Codex hooks only, without project hooks or trust bypass')
options=parser.parse_args()
if not options.run:parser.error('pass --run for this opt-in local runtime probe')
sys.path.insert(0,str(ROOT/'scripts/lib'))
from worker_record_clause import CLAUSE
from codex_thread_reader import runtime_binary
REPORT='Synthetic report. Discarded: none. Noticed: fixture. Unverified: external model compliance.'
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        req=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('/count_tokens'):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"input_tokens":10}');return
        self.server.requests.append(req)
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        if self.path.split('?',1)[0].endswith('/messages'):
            msg={'id':'msg_fixture','type':'message','role':'assistant','model':req['model'],'content':[], 'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':10}}
            events=[('message_start',{'message':msg}),('content_block_start',{'index':0,'content_block':{'type':'text','text':''}}),('content_block_delta',{'index':0,'delta':{'type':'text_delta','text':REPORT}}),('content_block_stop',{'index':0}),('message_delta',{'delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':10}}),('message_stop',{})]
        else:
            item={'id':'msg_fixture','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':REPORT,'annotations':[]}]}
            response={'id':'resp_fixture','object':'response','created_at':1,'status':'completed','model':req['model'],'output':[item],'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}}
            events=[('response.created',{'response':dict(response,status='in_progress',output=[])}),('response.output_item.done',{'output_index':0,'item':item}),('response.completed',{'response':response})]
        for name,data in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(dict(data,type=name))+'\n\n').encode());self.wfile.flush()
    def do_CONNECT(self):
        self.send_error(403,'Probe allows loopback provider only')
    def log_message(self,*a):pass

def texts(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for v in value.values():yield from texts(v)
    elif isinstance(value,list):
        for v in value:yield from texts(v)

with tempfile.TemporaryDirectory(prefix='worker-context-fixture-') as td:
    root=Path(td).resolve()
    if not options.installed_codex_hooks:(root/'.codex').mkdir()
    subprocess.run(['git','-C',str(root),'init','-q'],check=True)
    if not options.installed_codex_hooks:
        (root/'.codex/config.toml').write_text('')
    chook=shlex.quote(sys.executable)+' '+shlex.quote(str(ROOT/'codex/hooks/worker_record_context.py'))
    if not options.installed_codex_hooks:
        (root/'.codex/hooks.json').write_text(json.dumps({'hooks':{e:[{'hooks':[{'type':'command','command':chook,'timeout':5}]}] for e in ('UserPromptSubmit','Stop')}}))
    ahook=shlex.quote(sys.executable)+' '+shlex.quote(str(ROOT/'hooks/codex-parent-worker-record-nudge.py'))
    aset=root/'claude-settings.json'
    if not options.installed_codex_hooks:
        aset.write_text(json.dumps({'hooks':{e:[{'hooks':[{'type':'command','command':ahook,'timeout':5}]}] for e in ('UserPromptSubmit','Stop')}}))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.requests=[]
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    env={k:v for k,v in os.environ.items() if not k.startswith(('OPENAI_','ANTHROPIC_')) and k not in ('CLAUDECODE','CLAUDE_CODE_SESSION_ID','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy')}
    env['CODEX_THREAD_ID']='11111111-1111-4111-8111-111111111111'
    env['CODEX_SESSION_ID']=env['CODEX_THREAD_ID']
    env.update(WRAP_TEST_KEY='synthetic-local-only',ANTHROPIC_API_KEY='synthetic-local-only',ANTHROPIC_BASE_URL=base,
               CLAUDE_CONFIG_DIR=str(root/'claude-config'),CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',CODEX_WORKER_RECORD_DIR=str(root/'records'))
    if options.installed_codex_hooks:
        env.update(HTTP_PROXY=base,HTTPS_PROXY=base,ALL_PROXY=base,NO_PROXY='127.0.0.1,localhost')
    cb=runtime_binary(options.codex)
    cargs=[cb,'-a','never','exec','--ephemeral','--skip-git-repo-check','--json','-C',str(root),
           '-c','model="fixture"','-c','model_provider="wrap_probe"','-c','model_providers.wrap_probe.name="wrap_probe"',
           '-c',f'model_providers.wrap_probe.base_url="{base}"','-c','model_providers.wrap_probe.wire_api="responses"',
           '-c','model_providers.wrap_probe.env_key="WRAP_TEST_KEY"','-c','model_providers.wrap_probe.request_max_retries=0',
           '-c','model_providers.wrap_probe.stream_max_retries=0','-c','developer_instructions="ORIGINAL_SYSTEM_SENTINEL"',
           '-c','project_doc_max_bytes=0']
    if not options.installed_codex_hooks:
        cargs+=['--dangerously-bypass-hook-trust','-c',f'projects.{json.dumps(str(root))}.trust_level="trusted"']
    aargs=['claude','-p','--model','claude-sonnet-4-5','--system-prompt','ORIGINAL_SYSTEM_SENTINEL','--setting-sources','project',
           '--settings',str(aset),'--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--max-turns','1']
    try:
        vendors=(('codex',cargs),) if options.installed_codex_hooks else (('codex',cargs),('claude',aargs))
        for vendor,args in vendors:
            for delegated in (True,False):
                runenv=dict(env)
                if not delegated:
                    runenv.pop('CODEX_THREAD_ID',None);runenv.pop('CODEX_SESSION_ID',None)
                server.requests=[]
                p=subprocess.run(args+['ORIGINAL_TASK_SENTINEL'],cwd=root,env=runenv,input='',capture_output=True,text=True,timeout=50)
                flat='\n'.join(t for req in server.requests for t in texts(req))
                good=p.returncode==0 and bool(server.requests) and 'ORIGINAL_SYSTEM_SENTINEL' in flat and 'ORIGINAL_TASK_SENTINEL' in flat and (CLAUSE.strip() in flat)==delegated
                print(json.dumps({'vendor':vendor,'delegated':delegated,'exit':p.returncode,'request':bool(server.requests),'clause':CLAUSE.strip() in flat,'originals':all(x in flat for x in ('ORIGINAL_SYSTEM_SENTINEL','ORIGINAL_TASK_SENTINEL')),'installed_codex_hooks':options.installed_codex_hooks,'trust_bypass':'--dangerously-bypass-hook-trust' in args,'ok':good}),flush=True)
                if p.returncode:print('cli stderr:',p.stderr[-1800:]);print('cli stdout:',p.stdout[-1000:])
                if not good:raise AssertionError('worker context check failed')
        server.requests=[]
        p=subprocess.run(cargs+['-'],cwd=root,env=env,input='',capture_output=True,text=True,timeout=30)
        assert not server.requests
        print('OK: empty Codex stdin starts no model request (CLI exit:',p.returncode,')')
        from worker_observations import read,claude_reports
        rows,errs=read(env['CODEX_THREAD_ID'],root/'records')
        if options.installed_codex_hooks:
            phases={r.get('phase') for r in rows if r.get('vendor')=='codex'}
            print('installed Codex observations:',len(rows),'phases:',sorted(phases),'errors:',errs)
            assert phases>={'prompt','stop'} and not errs
        else:
            reports,errs2=claude_reports(rows)
            print('observations:',len(rows),'claude reports:',len(reports),'errors:',errs+errs2)
            assert reports and REPORT in reports[-1]['text'] and not errs and not errs2
    finally:
        server.shutdown();server.server_close()
