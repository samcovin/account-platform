#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline source hygiene; --initial-import adds one-time transfer checks."""
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

DOCUMENTATION_HOSTS = {
    'apps.nextcloud.com', 'www.w3.org', 'www.gnu.org', 'www.7-zip.org',
    'fsf.org', 'www.fsf.org', 'gnu.org', 'www.affero.org', 'opensource.org',
    'spdx.org', 'raw.githubusercontent.com',
    'docs.nextcloud.com', 'docs.github.com',
}
SECRET_PATTERNS = {
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----',
    'github-token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
    'aws-access-key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'slack-token': rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
    'jwt': rb'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{20,}\b',
    'credential-in-url': rb'\b[a-z]+://[^\s/<>\x22\x27:@]+:[^\s/<>\x22\x27@]+@',
}
FORBIDDEN_PARTS = {
    'history', 'candidates', 'private', 'backups', 'exports', 'runtime',
    '.aws', '.codex', '.agents', 'node_modules', '__pycache__',
}
FORBIDDEN_NAMES = {
    '.env', '.ingress-secret', 'mailcow.conf', 'config.php',
    'FETCH_HEAD', 'ORIG_HEAD', 'IMPORT_SHA256SUMS',
}
FORBIDDEN_SUFFIXES = (
    '.sql', '.sql.gz', '.pem', '.key', '.p12', '.pfx', '.kdbx', '.log',
    '.tar', '.tar.gz', '.tgz', '.zip', '.bak', '.dump', '.pyc', '.bundle',
)


def inspect_file(path, data, *, initial_import=False):
    """Return categories only; never include matched secret values."""
    errors = []
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ''
    if (any(part in FORBIDDEN_PARTS for part in parts)
            or name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES)
            or (name.startswith('.env.') and name != '.env.example')):
        errors.append('excluded-file')
    try:
        value = data.decode('utf-8')
    except UnicodeDecodeError:
        return errors + ['non-text-file']
    if '\0' in value:
        errors.append('binary-content')
    for category, pattern in SECRET_PATTERNS.items():
        if re.search(pattern, data):
            errors.append(category)
    if initial_import:
        if re.search(rb'/home/[A-Za-z0-9_.-]+/', data):
            errors.append('personal-home-path')
        # Reserved-example constraints apply only before work configuration.
        normalized = value.replace('\\.', '.')
        hosts = re.findall(
            r'(?<![\w.-])(?:[A-Za-z0-9-]+\.)+(?:email|sbs|com|org|net|io|gov|edu|local|lan)\b',
            normalized,
        )
        for host in hosts:
            if host != 'user.email' and host.lower() not in DOCUMENTATION_HOSTS:
                errors.append('non-example-hostname')
                break
        for ip in re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', value):
            if ip not in {'127.0.0.1', '0.0.0.0'}:
                errors.append('infrastructure-address')
                break
        if not path.endswith(('/LICENSE', '.md')) and re.search(r'\bFamily\s+Services\b', value):
            errors.append('personal-branding')
    if path.endswith('.xml') or path.endswith('.svg'):
        try:
            ET.fromstring(data)
        except ET.ParseError:
            errors.append('invalid-xml')
    return sorted(set(errors))


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def scan_repository(root, *, initial_import=False):
    errors = []
    if initial_import:
        if git(root, 'remote').strip():
            errors.append('repository: unexpected remote at initial import')
        git_dir = root / '.git'
        if not git_dir.is_dir() or git_dir.is_symlink():
            errors.append('repository: initial import requires a fresh standalone Git directory')
        for relative in ('objects/info/alternates', 'shallow', 'info/grafts'):
            if (git_dir / relative).exists():
                errors.append('repository: inherited history dependency at initial import')
        if git(root, 'for-each-ref', '--format=%(refname)').strip():
            errors.append('repository: existing refs at initial import')
        local_keys = git(root, 'config', '--local', '--name-only', '--list').decode().lower().splitlines()
        if any(key in {'user.name', 'user.email', 'core.hookspath', 'commit.gpgsign'} for key in local_keys):
            errors.append('repository: local author/hook/signing override at initial import')
    # Scan every stored object, including unreachable objects. This repository is
    # built from sanitized bytes, rather than deleting private files after import.
    objects = git(root, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)').decode().splitlines()
    blobs = commits = 0
    for entry in objects:
        oid, kind = entry.split()
        if kind == 'blob':
            blobs += 1
            for category in inspect_file('object.txt', git(root, 'cat-file', 'blob', oid), initial_import=initial_import):
                # Notices are checked in their real path below.
                if category != 'personal-branding':
                    errors.append(f'blob {oid[:12]}: {category}')
        elif kind == 'commit':
            commits += 1
            metadata = git(root, 'cat-file', 'commit', oid)
            if initial_import:
                errors.append(f'commit {oid[:12]}: existing history at initial import')
            # Work author identities, remotes and real service domains are normal
            # after import. Credential patterns remain errors in either mode.
            errors.extend(f'commit {oid[:12]}: {category}' for category in inspect_file('commit.txt', metadata, initial_import=initial_import))
            for entry in git(root, 'ls-tree', '-rz', '--full-tree', oid).split(b'\0'):
                if not entry:
                    continue
                meta, raw_path = entry.split(b'\t', 1)
                mode, entry_kind, _ = meta.decode().split()
                path = raw_path.decode()
                if mode not in {'100644', '100755'} or entry_kind != 'blob':
                    errors.append(f'commit {oid[:12]}:{path}: unexpected file mode')
                errors.extend(f'commit {oid[:12]}:{path}: {category}' for category in inspect_file(path, b'') if category == 'excluded-file')
    refs = git(root, 'for-each-ref', '--format=%(refname)', 'refs/heads').decode().splitlines()
    checked = 0
    for ref in refs:
        for entry in git(root, 'ls-tree', '-rz', '--full-tree', ref).split(b'\0'):
            if not entry:
                continue
            meta, raw_path = entry.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            path = raw_path.decode()
            checked += 1
            if mode not in {'100644', '100755'} or kind != 'blob':
                errors.append(f'{ref}:{path}: unexpected file mode')
                continue
            errors.extend(f'{ref}:{path}: {category}' for category in inspect_file(path, git(root, 'cat-file', 'blob', oid), initial_import=initial_import))
    tracked = set()
    for entry in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, oid, stage = meta.decode().split()
        path = raw_path.decode()
        tracked.add(path)
        if mode not in {'100644', '100755'} or stage != '0':
            errors.append(f'index:{path}: unexpected file mode or unresolved merge')
        errors.extend(f'index:{path}: {category}' for category in inspect_file(path, git(root, 'cat-file', 'blob', oid), initial_import=initial_import))
    paths = root.rglob('*') if initial_import else (root / path for path in sorted(tracked))
    for path in paths:
        relative = path.relative_to(root)
        if '.git' in relative.parts:
            continue
        if path.is_symlink():
            errors.append(f'{relative}: symlink')
        elif path.is_file():
            errors.extend(f'{relative}: {category}' for category in inspect_file(str(relative), path.read_bytes(), initial_import=initial_import))
    return errors, {'branches': len(refs), 'branch_files': checked, 'staged_files': len(tracked), 'stored_blobs': blobs, 'stored_commits': commits}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial-import', action='store_true',
                        help='one-time check before the first work commit/remote/configuration')
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors, counts = scan_repository(args.root.resolve(), initial_import=args.initial_import)
    print('Handoff checks: ' + ', '.join(f'{k}={v}' for k, v in counts.items()))
    if errors:
        print('\n'.join(errors))
        return 1
    mode = 'initial import' if args.initial_import else 'tracked source and Git object hygiene'
    print(f'PASS: limited offline {mode} checks. This is not a security audit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
