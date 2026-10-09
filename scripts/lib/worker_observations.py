"""Machine-local worker observations for a Codex parent; metadata, not authority.

# agent-authority:file

The runtime-provided CODEX_THREAD_ID identifies an ancestor for headless CLIs;
it is not a human approval or a cryptographically authenticated direct edge.
Store only identities, prompt/report hashes and bounded transcript positions.
Never store internal reasoning, prompt bodies or approval statements here.
Collected observations can be pruned after 30 days; uncollected observations are
kept and remain visible to wrap. Native subagents use their explicit parent ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

SID = re.compile(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z')
RETENTION = 30 * 86400


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def record_dir():
    path=Path(os.environ.get('CODEX_WORKER_RECORD_DIR') or
              (Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'state/worker-observations')).expanduser()
    if not path.is_absolute():raise ValueError('worker record directory must be absolute')
    return path


def codex_parent(event, vendor):
    parent = os.environ.get('CODEX_THREAD_ID') or os.environ.get('CODEX_SESSION_ID') or ''
    child = event.get('session_id')
    if not SID.fullmatch(parent) or not isinstance(child,str) or not SID.fullmatch(child):
        return None
    if vendor == 'codex' and parent == child:
        return None
    return parent


def position(path):
    if not isinstance(path,str) or not Path(path).is_absolute():
        return None
    try:
        stat = Path(path).stat()
        if not Path(path).is_file():
            return None
        return {'path':str(Path(path).resolve()), 'device':stat.st_dev,
                'inode':stat.st_ino, 'offset':stat.st_size}
    except FileNotFoundError:
        return {'path':str(Path(path).resolve()), 'device':None,'inode':None,'offset':0}
    except OSError:
        return None


def write(parent, row, directory=None, ident=None):
    if not isinstance(parent,str) or not SID.fullmatch(parent):
        return
    target = (Path(directory) if directory is not None else record_dir())/digest(parent)
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    ident = ident or uuid.uuid4().hex
    if not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('invalid observation id')
    value = dict(row,version=1,parent=parent,id=ident,recorded_ns=time.time_ns(),
                 recorded_at=datetime.now(timezone.utc).isoformat())
    fd, temporary = tempfile.mkstemp(prefix='.',dir=target)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary,target/(ident+'.json'))
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def observe(event, vendor, phase, parent=None, directory=None):
    if parent is None and phase.startswith('subagent_'):return
    parent = parent or codex_parent(event,vendor)
    if parent is None:return
    child = event.get('agent_id') if phase.startswith('subagent_') else event.get('session_id')
    if not isinstance(child,str) or not SID.fullmatch(child):return
    prompt = event.get('prompt')
    report = event.get('last_assistant_message')
    path = event.get('agent_transcript_path') if phase in ('subagent_stop','claude_agent_stop','claude_agent_start') else event.get('transcript_path')
    write(parent, {'vendor':vendor,'child':child,'phase':phase,'turn':event.get('turn_id'),
                   'cwd':event.get('cwd'),'position':position(path),
                   'agent':event.get('agent_id') if phase.startswith('claude_agent_') else None,
                   'prompt_hash':digest(prompt) if isinstance(prompt,str) else None,
                   'report_hash':digest(report) if isinstance(report,str) and report else None},directory)


def read(parent, directory=None):
    if not isinstance(parent,str) or not SID.fullmatch(parent):return [],['invalid parent identity']
    target = (Path(directory) if directory is not None else record_dir())/digest(parent)
    rows, errors = [], []
    if target.is_symlink():return [],['observation directory is a symlink']
    try:
        with os.scandir(target) as entries:
            paths=sorted(Path(p.path) for p in entries if p.name.endswith('.json'))
    except FileNotFoundError:
        return [],[]
    except OSError as exc:
        return [],[type(exc).__name__]
    for path in paths:
        if path.name=='collected.json':continue
        try:
            if path.is_symlink():raise ValueError('observation symlink')
            row=json.loads(path.read_text(encoding='utf-8'))
            if (row.get('version')!=1 or row.get('parent')!=parent or
                    path.stem!=row.get('id') or not re.fullmatch('[0-9a-f]{32}',row['id']) or
                    row.get('vendor') not in ('codex','claude') or
                    (row.get('phase')!='expected' and not SID.fullmatch(row.get('child',''))) or
                    row.get('phase') not in ('prompt','stop','subagent_start','subagent_stop','claude_agent_start','claude_agent_stop','expected') or
                    type(row.get('recorded_ns')) is not int):
                raise ValueError('unrecognized observation')
            allowed={'version','parent','id','recorded_ns','recorded_at','vendor','child','phase','turn','cwd','position','prompt_hash','report_hash','tool','index','command_hash','reasons','agent'}
            if set(row)-allowed:raise ValueError('unknown observation fields')
            rows.append(row)
        except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
            errors.append(path.name+': '+type(exc).__name__)
    return sorted(rows,key=lambda x:x['recorded_ns']), errors


def claude_reports(rows):
    """Only the byte ranges observed during this parent's worker invocations."""
    reports, errors = [], []
    starts = {}
    for row in rows:
        if row['vendor']!='claude':continue
        key = row['child']
        if row['phase']=='prompt':
            starts[key] = row
        elif row['phase'] in ('stop','claude_agent_stop'):
            agent_stop=row['phase']=='claude_agent_stop'
            begin=starts.get(key) if agent_stop else starts.pop(key,None)
            a = begin.get('position') if begin else None
            b = row.get('position')
            after_ns=None
            if agent_stop and b:
                after_ns=begin['recorded_ns'] if begin else None
                if not row.get('report_hash') and after_ns is None:
                    errors.append('Claude subagent scope unavailable: '+str(row.get('agent')))
                    continue
                a=dict(b,offset=0,device=None,inode=None)
            if not a or not b or a['path']!=b['path'] or a['offset']>b['offset']:
                errors.append('Claude report range unavailable: '+key)
                continue
            try:
                path=Path(b['path'])
                stat=path.stat()
                hash_only=False
                if (stat.st_dev,stat.st_ino)!=(b['device'],b['inode']) or stat.st_size<b['offset']:
                    if not row.get('report_hash'):raise ValueError('transcript rotated or truncated')
                    hash_only=True  # Some CLI builds flush the transcript only after Stop.
                if a['inode'] is not None and (a['device'],a['inode'])!=(b['device'],b['inode']):
                    if not row.get('report_hash'):raise ValueError('transcript replaced within invocation')
                    hash_only=True
                with path.open('rb') as stream:
                    stream.seek(0 if hash_only else a['offset'])
                    data=stream.read() if hash_only else stream.read(b['offset']-a['offset'])
                last = None
                for line in data.decode('utf-8').splitlines():
                    obj=json.loads(line)
                    if obj.get('type')!='assistant':continue
                    if after_ns is not None and not row.get('report_hash'):
                        stamp=obj.get('timestamp')
                        if not isinstance(stamp,str):continue
                        try:created=int(datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()*1_000_000_000)
                        except ValueError:continue
                        if created<after_ns:continue
                    blocks=(obj.get('message') or {}).get('content')
                    if isinstance(blocks,list):
                        text='\n'.join(x['text'] for x in blocks if isinstance(x,dict) and x.get('type')=='text' and isinstance(x.get('text'),str))
                        if text and (not hash_only or digest(text)==row['report_hash']):last=text
                if last is None:raise ValueError('no visible assistant report in observed range')
                if row.get('report_hash') and digest(last)!=row['report_hash']:
                    raise ValueError('visible report does not match Stop observation')
                reports.append({'vendor':'claude','child':key,'agent':row.get('agent'),'text':last,'source':b['path'],'observation':row['id']})
            except (OSError,ValueError,UnicodeError,TypeError) as exc:
                errors.append('Claude report unreadable: '+key+' ('+type(exc).__name__+': '+str(exc)+')')
    errors.extend('Claude worker still has no Stop observation: '+key for key in starts)
    return reports,errors


def mark_collected(parent, reference, directory=None):
    rows, errors=read(parent,directory)
    if errors:raise ValueError('unreadable observations cannot be marked collected')
    if not isinstance(reference,str) or not reference.strip():raise ValueError('durable reference required')
    target=(Path(directory) if directory is not None else record_dir())/digest(parent)
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    value={'version':1,'parent':parent,'ids':[r['id'] for r in rows],
           'reference':reference,'collected_ns':time.time_ns()}
    fd,tmp=tempfile.mkstemp(prefix='.',dir=target)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False)
        os.replace(tmp,target/'collected.json')
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def prune_collected(directory=None,now_ns=None):
    root=Path(directory) if directory is not None else record_dir()
    cutoff=(now_ns if now_ns is not None else time.time_ns())-RETENTION*1_000_000_000
    removed=0
    if root.is_symlink():return 0
    for marker in root.glob('*/collected.json'):
        try:
            if marker.is_symlink() or marker.parent.is_symlink():continue
            data=json.loads(marker.read_text())
            if (data.get('version')!=1 or type(data.get('collected_ns')) is not int or data['collected_ns']>=cutoff
                    or not isinstance(data.get('ids'),list) or not isinstance(data.get('reference'),str) or not data['reference']):continue
            if not isinstance(data.get('parent'),str) or not SID.fullmatch(data['parent']) or marker.parent.name!=digest(data['parent']):continue
            for ident in data['ids']:
                if not isinstance(ident,str) or not re.fullmatch('[0-9a-f]{32}',ident):continue
                path=marker.parent/(ident+'.json')
                if not path.is_symlink() and path.is_file() and path.stat().st_mtime_ns<cutoff:
                    row=json.loads(path.read_text())
                    if row.get('id')==ident and row.get('parent')==data['parent'] and type(row.get('recorded_ns')) is int and row['recorded_ns']<=data['collected_ns']:
                        path.unlink();removed+=1
            if all(isinstance(i,str) and re.fullmatch('[0-9a-f]{32}',i) and not (marker.parent/(i+'.json')).exists() for i in data['ids']):
                marker.unlink()
                try:marker.parent.rmdir()
                except OSError:pass
        except (OSError,ValueError,TypeError,KeyError):continue
    return removed
