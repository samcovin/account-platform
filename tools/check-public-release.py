#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Offline public-source review; --release also enforces pending human gates."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

REQUIRED_GATES = frozenset({
    'OWNERSHIP-REVIEW', 'APP-INTEGRATION-RIGHTS', 'SECURITY-POLICY',
    'PHP-VALIDATION', 'SERVICE-VALIDATION', 'PUBLICATION-APPROVAL',
})

SPEC = importlib.util.spec_from_file_location('handoff_review', Path(__file__).with_name('verify-handoff.py'))
HYGIENE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HYGIENE)


def license_for(path):
    if path.startswith('apps/covin_account_admin/'):
        return 'AGPL-3.0-or-later'
    if path == 'LICENSES/AGPL-3.0-or-later.txt':
        return 'LicenseRef-Verbatim-License-Document'
    return 'BSD-3-Clause'


def source_files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*')
            if '.git' not in p.relative_to(root).parts and (p.is_file() or p.is_symlink())}


def check_tree(root, mapping):
    errors = []
    files = source_files(root)
    if not isinstance(mapping, dict):
        return ['license-map: invalid schema'], []
    entries = mapping.get('files', {})
    if (mapping.get('schema') != 1 or not isinstance(entries, dict)
            or not all(isinstance(entry, dict) for entry in entries.values())):
        return ['license-map: invalid schema'], []
    if set(files) != set(entries):
        errors.append('license-map: file coverage differs from the candidate')
    for relative, path in files.items():
        if relative in entries and entries[relative].get('license') != license_for(relative):
            errors.append(f'{relative}: incorrect license assignment')
        if path.is_symlink():
            errors.append(f'{relative}: unexpected symlink')
            continue
        if relative.split('/')[0] in {'private-audit', 'reference-0.4.0', 'preparation-evidence'}:
            errors.append(f'{relative}: private/reference material is excluded from the public source')
        errors.extend(f'{relative}: {category}' for category in
                      HYGIENE.inspect_file(relative, path.read_bytes(), initial_import=True))
    notices = mapping.get('preserved_notices', {})
    if not isinstance(notices, dict):
        errors.append('license-map: invalid notice pins')
        notices = {}
    required = {'LICENSE', 'apps/covin_account_admin/LICENSE', 'LICENSES/AGPL-3.0-or-later.txt'}
    if not required.issubset(notices):
        errors.append('license-map: mandatory notice pins are missing')
    for relative, expected in notices.items():
        if relative not in files:
            errors.append('license-map: required license notice file is missing')
        elif hashlib.sha256(files[relative].read_bytes()).hexdigest() != expected:
            errors.append(f'{relative}: required license notice changed or missing')
    try:
        metadata = ET.fromstring((root / 'apps/covin_account_admin/appinfo/info.xml').read_bytes())
        if metadata.findtext('licence') != 'agpl':
            errors.append('app metadata: retained AGPL declaration changed')
    except (OSError, ET.ParseError):
        errors.append('app metadata: missing or invalid')
    try:
        bsd = (root / 'LICENSE').read_text()
        if 'BSD 3-Clause License' not in bsd or 'Copyright (c) 2026, Sam Covin' not in bsd:
            errors.append('root license: expected authorized BSD notice missing')
    except OSError:
        errors.append('root license: missing')
    # Missing/empty/malformed gate data must never turn into implicit clearance.
    gates = mapping.get('release_gates')
    pending = []
    if not isinstance(gates, list) or not all(isinstance(g, dict) for g in gates):
        errors.append('release-gates: invalid or missing gate list')
    else:
        identifiers = [g.get('id') for g in gates]
        if (not all(isinstance(identifier, str) for identifier in identifiers)
                or len(identifiers) != len(REQUIRED_GATES)
                or set(identifiers) != REQUIRED_GATES):
            errors.append('release-gates: expected exactly one of each required gate')
        for gate in gates:
            status = gate.get('status')
            if not isinstance(status, str) or status not in {'pending', 'resolved'}:
                errors.append('release-gates: invalid gate status')
            if status != 'resolved':
                identifier = gate.get('id')
                pending.append(identifier if isinstance(identifier, str) and identifier in REQUIRED_GATES else 'INVALID-GATE')
                continue
            if not isinstance(gate.get('resolution'), str) or not gate['resolution'].strip():
                errors.append('release-gates: resolved gate lacks a resolution record')
            evidence = gate.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                errors.append('release-gates: resolved gate lacks evidence')
                continue
            for relative in evidence:
                if (not isinstance(relative, str) or relative not in files
                        or files[relative].is_symlink()):
                    errors.append('release-gates: resolved gate has invalid evidence path')
    # A clean worktree alone is insufficient for publishing a Git repository:
    # scan staged and historical objects too. Source-only archives need no Git.
    if (root / '.git').exists():
        history_errors, _ = HYGIENE.scan_repository(root)
        errors.extend('git: ' + message for message in history_errors)
    return sorted(set(errors)), pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true', help='fail while owner/security/integration gates remain open')
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        mapping = json.loads((root / 'LICENSE-MAP.json').read_text())
        errors, pending = check_tree(root, mapping)
    except (OSError, ValueError, TypeError, KeyError):
        print('FAIL: public license map is missing or invalid; inspect it locally.')
        return 1
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'PASS: public source hygiene and license coverage ({len(mapping["files"])} files).')
    if pending:
        print('OPEN release gates: ' + ', '.join(pending))
        if args.release:
            print('NOT CLEARED FOR RELEASE. No publication action was taken.')
            return 2
    print('This is an offline check, not a complete legal/security review or deployment approval.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
