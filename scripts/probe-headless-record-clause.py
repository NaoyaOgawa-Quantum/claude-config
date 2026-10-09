#!/usr/bin/env python3
"""probe-headless-record-clause.py — 実 CLI の送信内容と hook 発火を loopback の模擬応答で検証する手動 probe。

Run explicitly with --run [--mode argv|harness|all] [--repo CHECKOUT]. Requires
installed Claude and Codex CLIs for argv mode, Claude for harness mode. It sends
synthetic prompts to a loopback HTTP server, using a dummy key and an isolated
Claude config and working directory; no external model generation is requested.
Codex ignores user config/rules and uses an ephemeral run with an explicit local
provider. Do not run through a proxy; the subprocess environment drops proxy and
provider override variables. The harness grants Bash only to run a fake worker
which prints argv. It never reads existing transcripts or changes installed hooks.

argv: verify original system/task/stdin and the clause in real request bodies;
contrast duplicate Claude append flags and a Codex developer-instruction override
which replace the original system text. HTTP 400 ends the probe without a model.
harness: serve fixed synthetic SSE events to the real Claude CLI, verify its fake
Bash worker receives the clause, the saved parent log keeps the original command,
and the report reader joins that command to the actual execution receipt.

Results are JSON booleans, never request bodies or credentials. Exit 0 only after
all assertions; missing CLI, timeout or a changed protocol is failure, not success.
The result says nothing about external model compliance or other client builds.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def probe_env():
    # Preserve ordinary runtime paths, but isolate provider credentials/routing.
    return {k:v for k,v in os.environ.items()
            if not k.startswith(('ANTHROPIC_', 'OPENAI_', 'CLAUDE_'))
            and k not in ('CLAUDECODE','CODEX_THREAD_ID','CODEX_SESSION_ID','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY',
                          'http_proxy','https_proxy','all_proxy')}


def require_cli(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError('required CLI is missing: '+name)
    return path


class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        self.server.captured.append((self.path, body))
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"type":"error","error":{"type":"invalid_request_error","message":"synthetic probe complete"}}')

    def log_message(self, *args):
        pass


def probe_argv(repo, codex_path=None):
    with tempfile.TemporaryDirectory(prefix='headless-cli-probe-') as td:
        server = ThreadingHTTPServer(('127.0.0.1', 0), RequestHandler)
        server.captured = captured = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            env = dict(probe_env(), ANTHROPIC_API_KEY='synthetic-local-test',
                       ANTHROPIC_BASE_URL=base, CLAUDE_CONFIG_DIR=td,
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                       HEADLESS_TEST_API_KEY='synthetic-local-test')
            claude = [require_cli('claude'), '--bare', '--print', '--no-session-persistence',
                      '--model', 'claude-sonnet-4-5', '--append-system-prompt', 'ORIGINAL_SYSTEM_SENTINEL',
                      'ORIGINAL_TASK_SENTINEL']
            codex = [codex_path or require_cli('codex'), 'exec', '--ignore-user-config', '--ignore-rules',
                     '--ephemeral', '--skip-git-repo-check',
                     '-c', 'model="synthetic-model"',
                     '-c', 'model_provider="record_probe"',
                     '-c', 'model_providers.record_probe.name="record_probe"',
                     '-c', f'model_providers.record_probe.base_url="{base}"',
                     '-c', 'model_providers.record_probe.wire_api="responses"',
                     '-c', 'model_providers.record_probe.env_key="HEADLESS_TEST_API_KEY"',
                     '-c', 'model_providers.record_probe.request_max_retries=0',
                     '-c', 'model_providers.record_probe.stream_max_retries=0',
                     '-c', 'project_doc_max_bytes=0',
                     '-c', 'developer_instructions="ORIGINAL_SYSTEM_SENTINEL"']
            wrapped = [sys.executable, str(repo/'hooks/headless-record-clause-nudge.py'), '--run']
            cases = [('claude-system', wrapped+claude, '', True),
                     ('codex-argument', wrapped+codex+['ORIGINAL_TASK_SENTINEL'], 'ORIGINAL_STDIN_SENTINEL', True),
                     ('codex-stdin', wrapped+codex+['-'], 'ORIGINAL_TASK_SENTINEL\nORIGINAL_STDIN_SENTINEL', True),
                     ('claude-duplicate-flag', claude+['--append-system-prompt','記録の約束 replacement'], '', False),
                     ('codex-config-override', codex+['-c','developer_instructions="記録の約束 replacement"','ORIGINAL_TASK_SENTINEL'], '', False)]
            for name, args, stdin, preserve_system in cases:
                captured.clear()
                p = subprocess.run(args,
                                   cwd=td, env=env, input=stdin, text=True, capture_output=True, timeout=35)
                # JSON requests may escape non-ASCII, so decode before inspecting.
                text = '\n'.join(json.dumps(json.loads(body), ensure_ascii=False) for _, body in captured)
                verdict = {'probe': name, 'request_received': bool(captured),
                           'clause': '記録の約束' in text,
                           'original_task': 'ORIGINAL_TASK_SENTINEL' in text,
                           'original_system': 'ORIGINAL_SYSTEM_SENTINEL' in text,
                           'original_stdin': 'ORIGINAL_STDIN_SENTINEL' in text if stdin else None,
                           'exit': p.returncode}
                print(json.dumps(verdict, ensure_ascii=False), flush=True)
                assert verdict['request_received'] and verdict['clause'] and verdict['original_task'], verdict
                assert verdict['original_system'] == preserve_system, verdict
                assert not stdin or verdict['original_stdin'], verdict
            for name,stdin,want_request in [('codex-empty-stdin','',False),('codex-clause-only-stdin','記録の約束: discarded / noticed / unverified',True)]:
                captured.clear()
                p=subprocess.run(codex+['-'],cwd=td,env=env,input=stdin,text=True,capture_output=True,timeout=35)
                print(json.dumps({'probe':name,'request_received':bool(captured),'exit':p.returncode},ensure_ascii=False),flush=True)
                assert bool(captured)==want_request, name
        finally:
            server.shutdown()
            server.server_close()


class HarnessHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path.endswith('/count_tokens'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"input_tokens":100}')
            return
        got_result = any(isinstance(m.get('content'), list) and any(b.get('type') == 'tool_result' for b in m['content']) for m in request.get('messages', []))
        self.server.calls.append(got_result)
        block = {'type':'text','text':'synthetic probe done'} if got_result else {
            'type':'tool_use','id':'toolu_probe','name':'Bash',
            'input':{'command':"claude -p 'synthetic task' > receipt.json",'description':'Run synthetic fixture'}}
        message = {'id':'msg_probe','type':'message','role':'assistant','model':'claude-sonnet-4-5',
                   'content':[], 'stop_reason':None,'stop_sequence':None,
                   'usage':{'input_tokens':100,'output_tokens':10}}
        events = [('message_start', {'type':'message_start','message':message}),
                  ('content_block_start', {'type':'content_block_start','index':0,'content_block':dict(block, **({'text':''} if got_result else {'input':{}}))}),
                  ('content_block_delta', {'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':block['text']} if got_result else {'type':'input_json_delta','partial_json':json.dumps(block['input'])}}),
                  ('content_block_stop', {'type':'content_block_stop','index':0}),
                  ('message_delta', {'type':'message_delta','delta':{'stop_reason':'end_turn' if got_result else 'tool_use','stop_sequence':None},'usage':{'output_tokens':10}}),
                  ('message_stop', {'type':'message_stop'})]
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream')
        self.end_headers()
        for name, event in events:
            self.wfile.write(('event: '+name+'\ndata: '+json.dumps(event)+'\n\n').encode())
            self.wfile.flush()

    def log_message(self, *args):
        pass


def probe_harness(repo):
    with tempfile.TemporaryDirectory(prefix='record-harness-probe-') as td:
        root = Path(td)
        real_claude = require_cli('claude')
        fake = root/'claude'
        fake.write_text('#!'+sys.executable+'\nimport sys,json\nprint(json.dumps(sys.argv[1:],ensure_ascii=False))\n')
        fake.chmod(0o755)
        config = root/'cfg'
        config.mkdir()
        hook = repo/'hooks/headless-record-clause-nudge.py'
        settings = root/'settings.json'
        settings.write_text(json.dumps({'hooks':{'PreToolUse':[{'matcher':'Bash','hooks':[{'type':'command','command':shlex.quote(sys.executable)+' '+shlex.quote(str(hook)),'timeout':5}]}]}}))
        server = ThreadingHTTPServer(('127.0.0.1',0),HarnessHandler)
        server.calls = calls = []
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            env = dict(probe_env(), ANTHROPIC_API_KEY='synthetic-test',ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_port}',
                       CLAUDE_CONFIG_DIR=str(config),CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                       PATH=str(root)+os.pathsep+os.environ['PATH'])
            for k in ('CLAUDECODE','CLAUDE_CODE_SESSION_ID'):
                env.pop(k,None)
            p = subprocess.run([real_claude,'-p','synthetic parent task',
                                '--model','claude-sonnet-4-5','--system-prompt','Run the supplied synthetic fixture.',
                                '--setting-sources','project','--settings',str(settings),
                                '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--tools','Bash',
                                '--allowedTools','Bash','--permission-mode','dontAsk','--max-turns','3'],
                               cwd=root,env=env,stdin=subprocess.DEVNULL,text=True,capture_output=True,timeout=45)
            receipt=root/'receipt.json'
            received=json.loads(receipt.read_text()) if receipt.exists() else []
            print(json.dumps({'parent_exit':p.returncode,'tool_result_received':True in calls,
                              'fixture_ran':receipt.exists(),'clause_reached_child':'記録の約束' in json.dumps(received,ensure_ascii=False)},ensure_ascii=False))
            logs=list((config/'projects').glob('*/*.jsonl'))
            commands=[]
            for log in logs:
                for line in log.read_text().splitlines():
                    try:
                        obj=json.loads(line)
                    except ValueError:
                        continue
                    for block in (obj.get('message') or {}).get('content',[]):
                        if isinstance(block,dict) and block.get('type')=='tool_use' and block.get('name')=='Bash':
                            commands.append((log,block.get('input',{}).get('command','')))
            log=commands[0][0] if commands else None
            report=subprocess.run([sys.executable,str(repo/'scripts/headless-worker-reports.py'),log.stem,'--projects-dir',str(config/'projects')],env=env,text=True,capture_output=True) if log else None
            matched=bool(report and '注入記録: added' in report.stdout)
            original=any(command=="claude -p 'synthetic task' > receipt.json" for _,command in commands)
            print(json.dumps({'original_command_persisted':original,'reporter_joined_execution_receipt':matched},ensure_ascii=False))
            assert original and matched, 'actual harness correlation failed'
            assert p.returncode == 0 and True in calls and '記録の約束' in json.dumps(received,ensure_ascii=False)
        finally:
            server.shutdown()
            server.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', action='store_true', help='run the local CLI probes explicitly')
    ap.add_argument('--codex', help='explicit Codex binary for argv probes')
    ap.add_argument('--mode', choices=('argv','harness','all'), default='all')
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args()
    if not args.run:
        ap.print_help()
        return 0
    repo = args.repo.resolve()
    for path in ('hooks/headless-record-clause-nudge.py','scripts/headless-worker-reports.py'):
        if not (repo/path).is_file():
            ap.error('missing source: '+str(repo/path))
    try:
        if args.mode in ('argv','all'):
            probe_argv(repo,args.codex)
        if args.mode in ('harness','all'):
            probe_harness(repo)
    except (AssertionError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('probe failed: '+type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
