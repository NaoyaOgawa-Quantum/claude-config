#!/usr/bin/env python3
"""codex_personal_skills.py — explicitly selected personal skills: install derived links, audit, and restore missing links (--selftest).

# agent-authority:file

The selected layer owns codex/skills.json: {"version":1,"skills":{"name":"relative/folder"}}.
The folder and its SKILL.md must stay inside that marked layer. No private layer
is discovered. The generated global AGENTS.md header may supply an existing
explicit selection at SessionStart. No skill body is copied or returned as a
global instruction. Conflicting user files/links are reported, never replaced.
An empty explicit mapping retires only unchanged links recorded by this helper.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

STATE = 'claude-config-personal-skills.json'
NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')


def selection(user_dir: Path) -> Path | None:
    path = user_dir / 'AGENTS.md'
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    if '<!-- claude-config-codex: global-personal-composite -->' not in text:
        return None
    match = re.search(r'^<!-- personal-source: (.+) -->$', text, re.M)
    if not match or not Path(match[1]).is_absolute():
        raise ValueError('managed personal-source header is missing or invalid')
    return Path(match[1]).resolve()


def sources(personal: Path) -> dict[str, Path] | None:
    personal = personal.resolve()
    if not (personal / '.claude-personal-layer').is_file():
        raise ValueError('selected personal-layer marker is missing')
    manifest = personal / 'codex/skills.json'
    if not manifest.exists():
        return None
    if personal not in manifest.resolve().parents:
        raise ValueError('personal manifest leaves the selected layer')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'version', 'skills'} or data['version'] != 1 or not isinstance(data['skills'], dict):
        raise ValueError('invalid personal skill manifest')
    result = {}
    for name, relative in data['skills'].items():
        if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError('invalid personal skill name/path')
        folder = (personal / relative).resolve()
        skill = (folder / 'SKILL.md').resolve()
        if personal not in folder.parents or personal not in skill.parents:
            raise ValueError('personal skill leaves the selected layer')
        body = skill.read_text(encoding='utf-8')
        front = body.split('---', 2)
        if len(front) != 3 or front[0].strip() or not re.search(r'^name:\s*[\'"]?' + re.escape(name) + r'[\'"]?\s*$', front[1], re.M):
            raise ValueError('personal skill name does not match its manifest')
        result[name] = folder
    return result


def owned(user_dir: Path, personal: Path) -> dict[str, str]:
    path = user_dir / STATE
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError('personal skill state must not be a symlink')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('personal') != str(personal.resolve()) or not isinstance(data.get('skills'), dict):
        raise ValueError('personal skill state belongs to a different binding or is invalid')
    if any(not isinstance(n, str) or not NAME.fullmatch(n) or not isinstance(p, str) or not Path(p).is_absolute() for n, p in data['skills'].items()):
        raise ValueError('invalid generated skill state')
    if any(personal.resolve() not in Path(p).resolve().parents for p in data['skills'].values()):
        raise ValueError('generated skill state leaves the selected layer')
    return data['skills']


def inspect(personal: Path, user_dir: Path):
    wanted = sources(personal)
    if wanted is None:
        if (user_dir / STATE).exists():
            raise ValueError('selected personal skill manifest disappeared')
        return None, {}, []
    old = owned(user_dir, personal)
    operations = []
    for name, source in wanted.items():
        target = user_dir / 'skills' / name
        if target.is_symlink() and target.resolve() == source:
            continue
        if target.exists() or target.is_symlink():
            if not (target.is_symlink() and name in old and str(target.resolve()) == old[name]):
                raise ValueError('conflicting user skill: ' + str(target))
            operations.append(('replace', target, source))
        else:
            operations.append(('create', target, source))
    for name, source in old.items():
        if name in wanted:
            continue
        target = user_dir / 'skills' / name
        if target.is_symlink() and str(target.resolve()) == source:
            operations.append(('retire', target, None))
        elif target.exists() or target.is_symlink():
            raise ValueError('changed retired skill remains user-owned: ' + str(target))
    return wanted, old, operations


def ensure(personal: Path, user_dir: Path, mode='install') -> list[str]:
    wanted, old, operations = inspect(personal, user_dir)
    if wanted is None:
        return []
    messages = [f'{action}: {target}' for action, target, _ in operations]
    state = user_dir / STATE
    expected = {'version': 1, 'personal': str(personal.resolve()), 'skills': {n: str(p) for n,p in wanted.items()}}
    if not state.exists() or old != expected['skills']:
        messages.append('refresh: personal skill binding state')
    if mode != 'install' or not messages:
        return messages
    # All sources and all targets were validated before any derived file changes.
    (user_dir / 'skills').mkdir(parents=True, exist_ok=True)
    for action, target, source in operations:
        if action in ('replace', 'retire'):
            if not target.is_symlink() or str(target.resolve()) != old[target.name]:
                raise ValueError('skill changed during installation: '+str(target))
            target.unlink()
        if source is not None:
            try:
                target.symlink_to(source, target_is_directory=True)
            except FileExistsError:
                if not target.is_symlink() or target.resolve() != source:
                    raise
    fd, temporary = tempfile.mkstemp(prefix='.personal-skills-', dir=user_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(expected, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, state)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return messages


def session_check(user_dir: Path) -> str:
    """Restore declared links at an already-selected binding; surface every failure."""
    try:
        personal = selection(user_dir)
        if personal is None:
            return ''
        changes = ensure(personal, user_dir)
        return ('Restored selected personal skills: ' + '; '.join(changes)) if changes else ''
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return 'Personal skill wiring needs attention: ' + str(exc)


def selftest():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        personal, user = root/'personal', root/'user'
        (personal/'codex').mkdir(parents=True)
        (personal/'.claude-personal-layer').touch()
        (personal/'skill/finish').mkdir(parents=True)
        (personal/'skill/finish/SKILL.md').write_text('---\nname: finish\ndescription: fixture\n---\nCanonical fixture.\n')
        manifest = personal/'codex/skills.json'
        manifest.write_text(json.dumps({'version':1,'skills':{'finish':'skill/finish'}}))
        assert ensure(personal,user,'check')
        ensure(personal,user)
        assert (user/'skills/finish').resolve() == personal/'skill/finish'
        assert not ensure(personal,user,'check')
        (user/'AGENTS.md').write_text('<!-- claude-config-codex: global-personal-composite -->\n<!-- personal-source: '+str(personal)+' -->\n')
        (user/'skills/finish').unlink()
        assert session_check(user).startswith('Restored')
        assert not session_check(user)
        (user/'skills/finish').unlink()
        (user/'skills/finish').mkdir()
        assert 'conflicting' in session_check(user)
        (user/'skills/finish').rmdir()
        ensure(personal,user)
        manifest.write_text(json.dumps({'version':1,'skills':{}}))
        ensure(personal,user)
        assert not (user/'skills/finish').exists()
        outside = root/'outside'
        outside.mkdir()
        (outside/'SKILL.md').write_text('---\nname: finish\n---\n')
        manifest.write_text(json.dumps({'version':1,'skills':{'finish':'../outside'}}))
        assert 'leaves' in session_check(user)
        assert not (user/'skills/finish').exists()
        manifest.unlink()
        assert 'disappeared' in session_check(user)
        print('OK: fresh install, idempotence, restart repair, conflict, retirement and layer boundary')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--personal-layer', type=Path)
    ap.add_argument('--user-dir', type=Path, default=Path.home()/'.codex')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--preflight', action='store_true')
    ap.add_argument('--session', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.session:
        print(session_check(args.user_dir))
        return 0
    if args.personal_layer is None:
        ap.error('--personal-layer is required')
    try:
        changes = ensure(args.personal_layer, args.user_dir, 'check' if args.check or args.preflight else 'install')
        if not args.preflight:
            for message in changes:
                print(('MISSING: ' if args.check else 'Installed: ') + message)
        return 1 if args.check and changes else 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print('personal skill wiring: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
