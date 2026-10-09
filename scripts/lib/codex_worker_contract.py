"""Worker-side record contract for Codex-origin delegation. No command rewrites.

# agent-authority:file

Native subagents receive context at SubagentStart. Headless workers recognize
the CODEX_THREAD_ID already inherited from Codex's execution environment and
receive context at their own UserPromptSubmit. The parent executable, argv,
stdin and tool permission flow stay byte-for-byte unchanged.
Missing environment lineage, disabled hooks and opaque script launches remain
observable limits. Observations are workflow evidence, never approval evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from worker_record_clause import CLAUSE, MARKER
import worker_observations as records
import headless_record_clause as headless

UNSUPPORTED = {'--bare','--ignore-user-config','--setting-sources','--settings'}
CREATE_TOOLS = {'mcp__codex_app__create_thread', 'mcp__codex_app.create_thread'}


def output(event, text):
    return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':text}}


def handle(event, vendor='codex'):
    if not isinstance(event,dict):return None
    name=event.get('hook_event_name')
    if vendor=='codex' and name=='SubagentStart':
        warning=''
        try:records.observe(event,'codex','subagent_start',parent=event.get('session_id'))
        except Exception as exc:warning='\nWorker observation unavailable: '+type(exc).__name__
        return output(name,CLAUSE+warning)
    if vendor=='codex' and name=='SubagentStop':
        try:records.observe(event,'codex','subagent_stop',parent=event.get('session_id'))
        except Exception as exc:return {'systemMessage':'Worker observation unavailable: '+type(exc).__name__}
        return {}
    if vendor=='claude' and name in ('SubagentStart','SubagentStop'):
        parent=records.codex_parent(event,vendor)
        if parent is None:return None
        try:records.observe(event,vendor,'claude_agent_start' if name=='SubagentStart' else 'claude_agent_stop',parent=parent)
        except Exception as exc:return {'systemMessage':'Worker observation unavailable: '+type(exc).__name__}
        return {}
    if name in ('UserPromptSubmit','Stop'):
        parent=records.codex_parent(event,vendor)
        if parent is None:return {} if name=='Stop' else None
        if name=='UserPromptSubmit':
            prompt=event.get('prompt')
            if not isinstance(prompt,str) or not prompt.strip():return None
            warning=''
            try:records.observe(event,vendor,'prompt',parent=parent)
            except Exception as exc:warning='\nWorker observation unavailable: '+type(exc).__name__
            if MARKER in prompt:return output(name,warning) if warning else None
            return output(name,CLAUSE+warning)
        try:records.observe(event,vendor,'stop',parent=parent)
        except Exception as exc:return {'systemMessage':'Worker observation unavailable: '+type(exc).__name__}
        return {}
    if vendor=='codex' and name=='PreToolUse' and event.get('tool_name') in CREATE_TOOLS:
        inp=event.get('tool_input')
        prompt=inp.get('prompt') if isinstance(inp,dict) else None
        if not isinstance(prompt,str) or not prompt.strip():return None
        if not (MARKER in prompt and all(x in prompt for x in ('捨てた案','気づいた','確かめていない'))):
            return {'hookSpecificOutput':{'hookEventName':name,'permissionDecision':'deny',
                    'permissionDecisionReason':'許可された別sessionへの委譲には記録条項の3項目をpromptに含める。既存の依頼を保持して次の段を追加する。これは新しいtaskの作成許可ではない。'+CLAUSE}}
        return None
    if vendor=='codex' and name=='PreToolUse' and event.get('tool_name')=='Bash':
        inp=event.get('tool_input')
        command=inp.get('command') if isinstance(inp,dict) else None
        if not isinstance(command,str):return None
        try:commands=headless.shell_commands(command)
        except ValueError:
            return None  # The wrap reader keeps this uninspected syntax visible.
        warnings=[]
        index=0
        for words in commands:
            pos=headless.executable_index(words)
            args=[w.value for w in words[pos:]] if pos is not None else []
            kind=headless.worker_kind(args)
            if not kind:continue
            flags=[a.partition('=')[0] for a in args if isinstance(a,str)]
            reasons=sorted(set(flags)&UNSUPPORTED)
            if any(w.raw.startswith(('CODEX_HOME=','CLAUDE_CONFIG_DIR=')) for w in words[:pos]):
                reasons.append('alternate config directory')
            if any(w.value in ('-i','--ignore-environment') for w in words[:pos]):
                reasons.append('environment reset')
            tool=str(event.get('tool_use_id',''))
            try:
                records.write(event.get('session_id'),{'vendor':kind,'child':None,'phase':'expected',
                              'tool':tool,'index':index,'command_hash':records.digest(command),
                              'reasons':reasons},ident=records.digest(tool+'\0'+records.digest(command)+'\0'+str(index))[:32])
            except Exception as exc:warnings.append('observation unavailable: '+type(exc).__name__)
            index+=1
            if reasons:warnings.append(kind+': '+', '.join(reasons))
        if warnings:
            return output(name,'記録条項の自動到達を確認できない起動形式: '+'; '.join(warnings)+
                          '。元の許可判定を保つためcommandは変更しない。起動時の指示または成果物で3項目の記録を確認する。')
    return None


def main(vendor='codex'):
    try:
        result=handle(json.loads(sys.stdin.read() or '{}'),vendor)
        if result is not None:print(json.dumps(result,ensure_ascii=False))
    except Exception:
        # Faults must never authorize, block, alter or start a tool/model call.
        pass
    return 0
