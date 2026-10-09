"""Offline-first metadata and privacy gate for the public PR campaign.

No third-party libraries, no network unless --live, no credentials logged.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = 'davidpd89/ci-sandbox-tmp'
PARENT = 'research/public-reuse-parent'
RANGE = set(range(11, 57))
ROW = re.compile(r'^\| \[#(\d+)\]\((https://github\.com/[^)]+)\) \| ([^|]+) \|$', re.M)
SECRET = re.compile(
    r'(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,}|'
    r'AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{28,}|'
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
    r'(?i:(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|token))\s*[=:]\s*[^\s#]{8,})'
)
EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]+@([\w.-]+\.[a-zA-Z]{2,})(?![\w.-])')
BANNED_PATH = re.compile(r'(?i)(?:^|/)(?:\.env(?:\.|$)|\.git/|cache/|profiles?/|screenshots?/|historial(?:es)?/|(?:[^/]+\.(?:sqlite3?|db|pem|p12|key|pyc))$)')


def check_metadata(doc, protocol):
    errors = []
    children = doc.get('children', [])
    if doc.get('repository') != REPO or doc.get('parent_pr') != 10 or doc.get('parent_head') != PARENT:
        errors.append('campaign identity mismatch')
    if len(children) < 46:
        errors.append(f'expected at least 46 original children, got {len(children)}')
    nums = [p.get('number') for p in children]
    numbers = set(nums)
    if not RANGE.issubset(numbers) or len(numbers) != len(nums) or numbers != set(range(11, max(numbers, default=10) + 1)):
        errors.append('missing, out-of-sequence or duplicate PR numbers')
    rows = ROW.findall(protocol)
    rownums = [int(n) for n, _, _ in rows]
    if len(rows) != len(children) or set(rownums) != numbers or len(set(rownums)) != len(rownums):
        errors.append('protocol index is incomplete or duplicated')
    by_number = {int(n): (url, title.strip()) for n, url, title in rows}
    seen_heads, seen_objectives, seen_urls = set(), set(), set()
    for p in children:
        n = p.get('number')
        if not isinstance(n, int) or n not in numbers:
            continue
        expected = f'https://github.com/{REPO}/pull/{n}'
        if p.get('url') != expected or by_number.get(n, (None,))[0] != expected:
            errors.append(f'#{n}: incorrect or missing PR link')
        if str(p.get('objective', '')).strip().casefold() != by_number.get(n, ('', ''))[1].casefold():
            errors.append(f'#{n}: objective/index mismatch')
        head = p.get('head', '')
        if not isinstance(head, str) or not head.startswith(f'research/{n-10:02}-') or not re.fullmatch(r'research/\d{2,}-[a-z0-9]+(?:-[a-z0-9]+)*', head):
            errors.append(f'#{n}: branch naming mismatch')
        if p.get('base') != PARENT or p.get('state') not in ('open', 'closed'):
            errors.append(f'#{n}: base or state mismatch')
        if p.get('area') not in ('platform', 'capability', 'quality', 'operations', 'relationship', 'discovery', 'engagement', 'community', 'content', 'architecture', 'data', 'analytics'):
            errors.append(f'#{n}: unknown domain')
        if not isinstance(p.get('title'), str) or not p['title'].strip():
            errors.append(f'#{n}: empty title')
        if not re.fullmatch('[a-f0-9]{40}', str(p.get('head_sha', ''))):
            errors.append(f'#{n}: invalid snapshot SHA')
        objective = str(p.get('objective', '')).casefold().strip()
        if head in seen_heads or objective in seen_objectives or expected in seen_urls:
            errors.append(f'#{n}: duplicate head/objective/link')
        seen_heads.add(head)
        seen_objectives.add(objective)
        seen_urls.add(expected)
        related = p.get('related_prs', [])
        if not isinstance(related, list) or len(related) != len(set(related)) or n in related or not set(related).issubset(numbers):
            errors.append(f'#{n}: invalid related PR references')
    return errors


def check_privacy(paths, root=ROOT):
    errors = []
    for rel in paths:
        rel = str(rel).replace('\\', '/')
        if rel.startswith('/') or '..' in Path(rel).parts or BANNED_PATH.search(rel):
            errors.append(f'{rel}: forbidden path'); continue
        path = root / rel
        if not path.is_file():
            continue  # deleted paths cannot leak content in the new tree
        if path.stat().st_size > 2_000_000:
            errors.append(f'{rel}: oversized file, human inspection needed'); continue
        try:
            data = path.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            errors.append(f'{rel}: binary/unreadable, human inspection needed'); continue
        if SECRET.search(data):
            errors.append(f'{rel}: possible secret')
        for match in EMAIL.finditer(data):
            if match.group(1).lower() not in ('example.com', 'example.org', 'example.net', 'invalid'):
                errors.append(f'{rel}: non-synthetic email'); break
    return errors


def fetch_live(token=None, opener=urlopen):
    url = f'https://api.github.com/repos/{REPO}/pulls?state=all&per_page=100&page=1'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'campaign-metadata-validator'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    result = []
    for page in range(1, 11):
        with opener(Request(url.replace('page=1', f'page={page}'), headers=headers), timeout=20) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError('Invalid GitHub PR listing: fail closed')
        result.extend(batch)
        if len(batch) < 100:
            return {item['number']: item for item in result}
    raise ValueError('PR list exceeded 10 pages: fail closed')


def check_live(doc, live):
    errors, warnings = [], []
    parent = live.get(10)
    if parent is None or parent['base']['ref'] != 'main' or parent['head']['ref'] != PARENT or parent['state'] != 'open':
        errors.append('#10: changed parent/base or missing parent PR')
    for item in doc['children']:
        n = item['number']
        p = live.get(n)
        if not p:
            errors.append(f'#{n}: live PR missing (broken link)'); continue
        if p.get('html_url') != item['url'] or p['base']['ref'] != item['base'] or p['head']['ref'] != item['head']:
            errors.append(f'#{n}: live URL/base/head drift')
        if p['state'] != item['state'] or p['title'] != item['title']:
            errors.append(f'#{n}: title/state snapshot drift, refresh manifest')
        if p['head']['sha'] != item['head_sha']:
            warnings.append(f'#{n}: head SHA changed; re-evaluate reviews/checks before promotion')
    return errors, warnings


def check_child_deliverables(paths, root=ROOT):
    """Reject scope briefs presented as finished child implementations."""
    modified = [str(p).replace('\\', '/') for p in paths]
    research = [p for p in modified if p.startswith('docs/research/') and p.endswith('.md')]
    tests = [p for p in modified if p.startswith('tests/') and p.endswith('.py')]
    if not research or not tests:
        return ['child PR needs docs/research evidence and offline regression tests']
    headings = ('## Problema', '## Alternativas', '## Licencias y procedencia',
                '## Decisión', '## Pruebas', '## Retirada')
    for p in research:
        file = root / p
        if file.is_file():
            content = file.read_text(encoding='utf-8')
            if all(h in content for h in headings):
                return []
    return ['child research evidence missing required headings']


def changed_paths(base):
    cmd = ['git', 'diff', '--name-only', '-z', '--diff-filter=ACMR', base, 'HEAD', '--']
    data = subprocess.check_output(cmd, cwd=ROOT)
    return [p.decode('utf-8') for p in data.split(b'\0') if p]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='recheck URLs and branch refs against GitHub API')
    parser.add_argument('--changed-base', help='git ref to compare added/changed files for privacy hygiene')
    args = parser.parse_args(argv)
    doc = json.loads((ROOT / 'docs/open-source-scouting/children.json').read_text(encoding='utf-8'))
    protocol = (ROOT / 'docs/open-source-scouting/PROTOCOL.md').read_text(encoding='utf-8')
    errors = check_metadata(doc, protocol)
    scan = [p.relative_to(ROOT) for d in ('docs/open-source-scouting/fixtures', 'docs/research')
            for p in (ROOT / d).rglob('*') if p.is_file()]
    if args.changed_base:
        try:
            changed = changed_paths(args.changed_base)
            scan += changed
            if os.environ.get('GITHUB_BASE_REF') == PARENT:
                errors += check_child_deliverables(changed)
        except (subprocess.CalledProcessError, OSError) as exc:
            errors.append(f'cannot inspect changed paths: {type(exc).__name__}')
    errors += check_privacy(set(map(str, scan)))
    warnings = []
    if args.live:
        try:
            live = fetch_live(os.environ.get('GITHUB_TOKEN'))
            e, warnings = check_live(doc, live)
            errors.extend(e)
        except Exception as exc:
            errors.append(f'live verification unavailable: {type(exc).__name__}')
    print(f'campaign: {len(doc["children"])} children; {len(errors)} errors; {len(warnings)} warnings')
    for e in errors:
        print('FAIL:', e)
    for w in warnings:
        print('WARN:', w)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
