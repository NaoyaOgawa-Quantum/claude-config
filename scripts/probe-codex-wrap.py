#!/usr/bin/env python3
"""probe-codex-wrap.py — 新規native sessionでwrap入口・収集・commit・掲示板を合成検証する。--run。

Explicitly select the canonical personal layer and public board engine. Uses
localhost fixed Responses output, dummy credentials, temporary Git repositories
and local bare remotes. The generated host grants only the fixed collect/commit
commands; it declines other tool approvals. HTTPS proxy rejects external calls.
No external model inference. Native test threads remain synthetic test records.
Skill entry is supplied through the typed skill input; slash-menu UI rendering
and model judgment are not tested. Child context is delivered in its initial
assignment; automatic hook delivery is tested by probe-codex-worker-context.py.
"""
import json,os,subprocess,tempfile,threading,sys,shlex,time,re
import hashlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parent.parent
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',action='store_true')
parser.add_argument('--codex',default='auto')
parser.add_argument('--personal-layer',type=Path,required=True)
parser.add_argument('--board-engine',type=Path,required=True)
parser.add_argument('--output',type=Path)
options=parser.parse_args()
if not options.run:parser.error('pass --run for this opt-in runtime probe')
PERSONAL=options.personal_layer.resolve()
BOARD=options.board_engine.resolve()
CANONICAL_SKILL_TEXT=(PERSONAL/'skill/wrap/SKILL.md').read_text()
CANONICAL_SKILL_BODY=(CANONICAL_SKILL_TEXT.split('---',2)[2] if CANONICAL_SKILL_TEXT.startswith('---\n') else CANONICAL_SKILL_TEXT).strip()
assert CANONICAL_SKILL_BODY, 'canonical skill must have an instruction body'
CANONICAL_SKILL_SHA256=hashlib.sha256(CANONICAL_SKILL_TEXT.encode()).hexdigest()
sys.path.insert(0,str(ROOT/'scripts/lib'))
from worker_record_clause import CLAUSE
from codex_thread_reader import runtime_binary
BINARY=runtime_binary(options.codex)
REPORT='## 記録の約束\n捨てた案: なし\n途中で気づいたこと: synthetic fixture\n確かめていないこと: external inference'
ROOT_TEXT='Synthetic wrap fixture. /wrap $wrap. Exercise only the supplied local fixture and return its result.'

def flatten(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for x in value.values():yield from flatten(x)
    elif isinstance(value,list):
        for x in value:yield from flatten(x)

def git(path,*args):
    return subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True,check=True).stdout.strip()

class Handler(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        self.server.blocked_external+=1;self.send_error(403,'Fixture allows loopback provider only')
    def do_POST(self):
        req=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        inputs=req.get('input',[])
        users=['\n'.join(flatten(x.get('content',[]))) for x in inputs if isinstance(x,dict) and x.get('role')=='user']
        child=bool(users and 'SYNTHETIC_CHILD_FIXTURE' in users[-1])
        strings='\n'.join(flatten(req))
        if child:
            self.server.child_clause=CLAUSE.strip() in strings
            self.server.child_requests+=1
            item=self.message(REPORT,'child')
        else:
            # Verify the selected source, independent of a heading that may move
            # into the canonical generic procedure after a skill refactor.
            self.server.skill_seen|=CANONICAL_SKILL_BODY in strings
            outputs={x.get('call_id'):x.get('output','') for x in inputs if isinstance(x,dict) and x.get('type')=='function_call_output'}
            if 'call_spawn' not in outputs:
                item=self.function('spawn_agent',{'message':'SYNTHETIC_CHILD_FIXTURE. Return the synthetic report without using tools.'+CLAUSE,'fork_context':False},'call_spawn','multi_agent_v1')
            elif self.server.child_id is None:
                raw=outputs['call_spawn']
                try:out=json.loads(raw) if isinstance(raw,str) else raw
                except ValueError:out={}
                self.server.child_id=out.get('agent_id') or out.get('id')
                self.server.spawn_output=raw
                if not self.server.child_id:
                    item=self.message('fixture failed: no child identity','failed')
                else:
                    item=self.function('wait_agent',{'targets':[self.server.child_id],'timeout_ms':10000},'call_wait','multi_agent_v1')
            elif 'call_wait' not in outputs:
                item=self.function('wait_agent',{'targets':[self.server.child_id],'timeout_ms':10000},'call_wait','multi_agent_v1')
            else:
                missing=next((name for name in ('declare','collect','commit','release') if 'call_'+name not in outputs),None)
                if missing:
                    cmd=shlex.quote(sys.executable)+' '+shlex.quote(str(self.server.step_script))+' '+missing
                    tool_args={'cmd':cmd,'workdir':str(self.server.project),'max_output_tokens':1200}
                    if missing in ('collect','commit'):
                        tool_args.update(sandbox_permissions='require_escalated',justification='Fixed local fixture step: '+missing)
                    item=self.function('exec_command',tool_args,'call_'+missing)
                else:
                    self.server.step_outputs=outputs
                    item=self.message('SYNTHETIC_WRAP_FINISHED\n'+REPORT,'root-done')
        self.server.serial+=1
        resp={'id':'resp_'+str(self.server.serial),'object':'response','created_at':1,'status':'completed','model':req.get('model','fixture'),'output':[item],'usage':{'input_tokens':10,'output_tokens':10,'total_tokens':20}}
        events=[('response.created',{'response':dict(resp,status='in_progress',output=[])}),('response.output_item.done',{'output_index':0,'item':item}),('response.completed',{'response':resp})]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for name,data in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(dict(data,type=name))+'\n\n').encode());self.wfile.flush()
    def function(self,name,args,cid,namespace=None):
        result={'id':'fc_'+cid,'type':'function_call','name':name,'call_id':cid,'arguments':json.dumps(args)}
        if namespace:result['namespace']=namespace
        return result
    def message(self,text,label):
        return {'id':'msg_'+label+str(self.server.serial),'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':text,'annotations':[]}]}
    def log_message(self,*a):pass

with tempfile.TemporaryDirectory(prefix='codex-wrap-e2e-') as td:
    base=Path(td).resolve();workspace=base/'workspace';workspace.mkdir();remotes=base/'remotes';remotes.mkdir()
    project=workspace/'fixture-project';board=workspace/'fixture-board'
    for repo in (project,board):
        repo.mkdir();bare=remotes/(repo.name+'.git')
        subprocess.run(['git','init','--bare','-q','-b','main',str(bare)],check=True)
        subprocess.run(['git','init','-q','-b','main',str(repo)],check=True)
        git(repo,'config','user.name','Fixture');git(repo,'config','user.email','fixture@example.invalid')
        git(repo,'remote','add','origin',str(bare))
    (board/'board.json').write_text(json.dumps({'board_format':1,'audience':'owner','encryption':'none','branch':'main'}))
    git(board,'add','board.json');git(board,'commit','-q','-m','Initialize fixture board');git(board,'push','-q','-u','origin','main')
    (project/'AGENTS.md').write_text('# Fixture project\nRead CLAUDE.md and SESSION.md. Only operate on this synthetic project.\n')
    (project/'CLAUDE.md').write_text('# Synthetic project\nNo external services or real board.\n')
    (project/'SESSION.md').write_text('# Session\nSynthetic wrap test.\n')
    git(project,'add','AGENTS.md','CLAUDE.md','SESSION.md');git(project,'commit','-q','-m','Initialize fixture project');git(project,'push','-q','-u','origin','main')
    (project/'.codex').mkdir();(project/'.codex/config.toml').write_text('')
    hook=shlex.quote(sys.executable)+' '+shlex.quote(str(ROOT/'codex/hooks/worker_record_context.py'))
    (project/'.codex/hooks.json').write_text(json.dumps({'hooks':{event:[{'hooks':[{'type':'command','command':hook,'timeout':5}]}] for event in ('UserPromptSubmit','SubagentStart','SubagentStop','Stop')}}))
    # The candidate installer derives a real skill link from the selected personal manifest.
    env=dict(os.environ,CODEX_USER_DIR=str(project/'.agents'),CODEX_WORKSPACE_ROOT=str(base/'codex-workspace'),
             AGENT_BOARD_WORKSPACE=str(workspace),CODEX_WORKER_RECORD_DIR=str(base/'observations'))
    subprocess.run(['bash',str(ROOT/'scripts/setup-codex.sh'),'--personal-layer',str(PERSONAL)],env=env,capture_output=True,text=True,check=True)
    assert (project/'.agents/skills/wrap').resolve()==PERSONAL/'skill/wrap'
    step=base/'steps.py'
    step.write_text('''import os,sys,json,subprocess
from pathlib import Path
project=Path('''+repr(str(project))+'''); board=Path('''+repr(str(board))+''')
engine=Path('''+repr(str(BOARD))+'''); root=Path('''+repr(str(ROOT))+'''); base=Path('''+repr(str(base))+''')
sid=(base/'parent-id.txt').read_text().strip()
def run(args):
 p=subprocess.run(args,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 print(p.stdout.strip());return p.stdout
common=['--root',str(board),'--agent','codex','--session',sid,'--session-name','synthetic-wrap-fixture','--source',str(project),'--policy','ordinary','--project','fixture-project','--thread','2042-01-01-wrap-fixture']
mode=sys.argv[1]
if mode=='declare':
 run([sys.executable,str(engine),'touch',*common,'--summary','Synthetic wrap edit declaration','--path',str(project/'result.txt')])
elif mode=='collect':
 p=subprocess.run([sys.executable,str(root/'scripts/codex-wrap-inventory.py'),sid,'--json'],capture_output=True,text=True)
 print('collector exit:',p.returncode,'stderr:',p.stderr[-1200:])
 data=json.loads(p.stdout)
 (base/'inventory.json').write_text(json.dumps(data))
 print(json.dumps({'threads':len(data['threads']),'unavailable':data['unavailable'],'root_messages':len(data['threads'][0]['messages'])}))
elif mode=='commit':
 (project/'result.txt').write_text('Synthetic wrap result.\\n')
 run(['git','-C',str(project),'add','result.txt'])
 os.environ.update(CLAUDE_CONFIG_AGENT_SESSION='codex:'+sid,CLAUDE_CONFIG_AGENT_MODEL='fixture',CLAUDE_CONFIG_AGENT_EFFORT='unknown')
 run(['git','-C',str(project),'commit','-m','Record synthetic wrap result','--','result.txt'])
 run(['git','-C',str(project),'push','origin','main'])
 local=run(['git','-C',str(project),'rev-parse','HEAD']);remote=run(['git','-C',str(project),'ls-remote','origin','refs/heads/main'])
 assert local.strip()==remote.split()[0]
elif mode=='release':
 sha=subprocess.check_output(['git','-C',str(project),'rev-parse','HEAD'],text=True).strip()
 run([sys.executable,str(engine),'untouch',*common,'--reference','fixture-project@'+sha])
''')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.serial=0;server.child_id=None;server.child_requests=0;server.child_clause=False;server.skill_seen=False;server.spawn_output='';server.step_outputs={};server.blocked_external=0;server.step_script=step;server.project=project
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}'
    env={k:v for k,v in env.items() if not k.startswith(('OPENAI_','ANTHROPIC_'))}
    env.update(WRAP_TEST_KEY='synthetic-local-only',HTTPS_PROXY=url,HTTP_PROXY=url,ALL_PROXY=url,NO_PROXY='127.0.0.1,localhost,::1')
    role=base/'default-agent.toml';role.write_text('model = "fixture"\nmodel_provider = "wrap_probe"\n')
    overrides=['-c','model="fixture"','-c','model_provider="wrap_probe"','-c','model_providers.wrap_probe.name="wrap_probe"',
          '-c',f'model_providers.wrap_probe.base_url="{url}"','-c','model_providers.wrap_probe.wire_api="responses"','-c','model_providers.wrap_probe.env_key="WRAP_TEST_KEY"',
          '-c','model_providers.wrap_probe.request_max_retries=0','-c','model_providers.wrap_probe.stream_max_retries=0',
          '-c',f'agents.default.config_file={json.dumps(str(role))}', '-c',f'projects.{json.dumps(str(project))}.trust_level="trusted"']
    args=[BINARY,'--dangerously-bypass-hook-trust','app-server','--stdio',*overrides]
    try:
        import queue
        proc=subprocess.Popen(args,cwd=project,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        q=queue.Queue();events=[];errlines=[];approvals=[]
        def stdout_reader():
            for line in proc.stdout:
                try:q.put(json.loads(line))
                except ValueError:pass
        def stderr_reader():errlines.extend(proc.stderr.readlines())
        t1=threading.Thread(target=stdout_reader,daemon=True);t2=threading.Thread(target=stderr_reader,daemon=True);t1.start();t2.start()
        def send(value):proc.stdin.write(json.dumps(value)+'\n');proc.stdin.flush()
        def receive(ident=None,finished=False):
            until=time.monotonic()+120
            while True:
                msg=q.get(timeout=max(.1,until-time.monotonic()));events.append(msg)
                if msg.get('method')=='item/commandExecution/requestApproval' and 'id' in msg:
                    params=msg.get('params',{});command=params.get('command') or ''
                    tokens=shlex.split(command)
                    if len(tokens)==3 and Path(tokens[0]).name in ('zsh','bash','sh'):tokens=shlex.split(tokens[2])
                    ok=len(tokens)==3 and tokens[:2]==[sys.executable,str(step)] and tokens[2] in ('collect','commit') and params.get('threadId')==parent
                    approvals.append({'command':command,'accepted':ok})
                    send({'id':msg['id'],'result':{'decision':'accept' if ok else 'decline'}})
                    continue
                if ident is not None and msg.get('id')==ident:
                    if 'error' in msg:raise RuntimeError(msg['error'])
                    return msg['result']
                if finished and msg.get('method')=='turn/completed' and msg.get('params',{}).get('threadId')==parent:
                    return msg['params']['turn']
        send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'synthetic-wrap-fixture','version':'1'},'capabilities':{'experimentalApi':True}}});receive(1)
        send({'method':'initialized','params':{}})
        # Native skill identities use their canonical paths. An installed user
        # skill can shadow the fixture link, so select the enabled native entry
        # and verify its complete source rather than submitting an inactive alias.
        send({'id':10,'method':'skills/list','params':{'cwds':[str(project)],'forceReload':True}})
        listed=receive(10)
        matches=[skill for entry in listed.get('data',[]) for skill in entry.get('skills',[])
                 if skill.get('name')=='wrap' and skill.get('enabled')
                 and Path(skill.get('path','')).resolve()==PERSONAL/'skill/wrap/SKILL.md']
        assert matches, 'native skill list lacks the enabled canonical wrap entry'
        skill_path=matches[0]['path']
        assert hashlib.sha256(Path(skill_path).read_bytes()).hexdigest()==CANONICAL_SKILL_SHA256

        send({'id':2,'method':'thread/start','params':{'cwd':str(project),'model':'fixture','modelProvider':'wrap_probe','approvalPolicy':'on-request','sandbox':'workspace-write','threadSource':'synthetic-wrap-fixture','config':{'hooks':json.loads((project/'.codex/hooks.json').read_text())['hooks']}}})
        started=receive(2);parent=started['thread']['id'];(base/'parent-id.txt').write_text(parent)
        send({'id':3,'method':'turn/start','params':{'threadId':parent,'input':[{'type':'text','text':ROOT_TEXT},{'type':'skill','name':'wrap','path':skill_path}]}});receive(3)
        final=receive(finished=True)
        p=subprocess.CompletedProcess(args,0 if final.get('status')=='completed' else 1,json.dumps(events,ensure_ascii=False),'\n'.join(errlines))
        print('bounded fixture approvals:',approvals)
        print('fixture hook events:',[(e.get('params',{}).get('run',{}).get('eventName'),e.get('params',{}).get('run',{}).get('sourcePath'),e.get('params',{}).get('run',{}).get('status')) for e in events if e.get('method')=='hook/completed' and str(project) in e.get('params',{}).get('run',{}).get('sourcePath','')])
        print(json.dumps({'exit':p.returncode,'parent':parent,'child':server.child_id,'skill_seen':server.skill_seen,'canonical_skill_sha256':CANONICAL_SKILL_SHA256,'child_requests':server.child_requests,'child_clause':server.child_clause,'clause_route':'initial assignment in this app-server fixture','steps':list(server.step_outputs),'blocked_external':server.blocked_external},ensure_ascii=False))
        print('spawn response:',server.spawn_output)
        print('collect response:',str(server.step_outputs.get('call_collect'))[-2200:])
        print('commit response:',str(server.step_outputs.get('call_commit'))[-1000:])
        if (base/'inventory.json').exists():
            inventory=json.loads((base/'inventory.json').read_text());print('inventory:',{'threads':len(inventory['threads']),'unavailable':inventory['unavailable']})
        print('project head matches:',git(project,'rev-parse','HEAD')==git(project,'ls-remote','origin','refs/heads/main').split()[0])
        print('stderr tail:',p.stderr[-1200:])
        print('event tail:',p.stdout[-1800:])
        assert git(project,'show','HEAD:result.txt').strip()=='Synthetic wrap result.'
        assert git(project,'rev-parse','HEAD')==git(project,'ls-remote','origin','refs/heads/main').split()[0]
        for name in ('declare','collect','commit','release'):
            assert 'Process exited with code 0' in str(server.step_outputs['call_'+name])
        for name in ('declare','release'):
            assert 'posted ' in str(server.step_outputs['call_'+name])
        assert p.returncode==0 and server.skill_seen and server.child_clause and server.child_requests>0
        assert all('call_'+x in server.step_outputs for x in ('declare','collect','commit','release'))
        for name in ('declare','commit','release'):
            assert 'failed:' not in str(server.step_outputs['call_'+name])
        assert inventory['threads'] and len(inventory['threads'])>1
        if options.output:options.output.write_text(json.dumps({'parent':parent,'child':server.child_id,'skill_seen':server.skill_seen,'canonical_skill_sha256':CANONICAL_SKILL_SHA256,'child_clause':server.child_clause,'threads':len(inventory['threads']),'blocked_external':server.blocked_external}))
    finally:
        if 'proc' in locals() and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        server.shutdown();server.server_close()
