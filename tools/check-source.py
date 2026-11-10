#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Limited source hygiene and available syntax checks; never deploys anything."""
from pathlib import Path
import re
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
errors = []
checked = 0
secret_patterns = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
    re.compile(rb'\bAKIA[A-Z0-9]{16}\b'),
]
for p in sorted(root.rglob('*')):
    rel = p.relative_to(root)
    if '.git' in rel.parts:
        continue
    if p.is_symlink():
        errors.append(f'{rel}: unexpected symlink')
        continue
    if not p.is_file():
        continue
    if p.name in {'.ingress-secret', 'mailcow.conf', 'config.php', '.env'} or (
        p.name.startswith('.env.') and p.name != '.env.example'
    ) or p.name.endswith(('.sql', '.sql.gz', '.pem', '.key', '.p12', '.pfx', '.log', '.tar.gz', '.zip')):
        errors.append(f'{rel}: private/runtime/archive file requires exclusion')
    data = p.read_bytes()
    if any(pattern.search(data) for pattern in secret_patterns):
        errors.append(f'{rel}: possible credential; inspect privately')
    command = None
    if p.suffix == '.js' and shutil.which('node'):
        command = ['node', '--check', str(p)]
    elif (p.suffix == '.sh' or data.startswith(b'#!/usr/bin/env bash')) and shutil.which('bash'):
        command = ['bash', '-n', str(p)]
    elif p.suffix == '.php' and shutil.which('php'):
        command = ['php', '-l', str(p)]
    if command:
        result = subprocess.run(command, capture_output=True, text=True)
        checked += 1
        if result.returncode:
            errors.append(f'{rel}: syntax check failed (run checker for this file locally)')
for runtime in ('node', 'bash', 'php'):
    if not shutil.which(runtime):
        print(f'NOT RUN: {runtime} syntax checks; runtime unavailable')
print(f'Syntax checks completed: {checked}')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('No findings from limited source checks. Manual diff review is still required.')
