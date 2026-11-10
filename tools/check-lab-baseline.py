#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Validate a pinned external 0.4.0 source baseline; never starts services."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import xml.etree.ElementTree as ET

APP_ROOT = 'apps/covin_account_admin'
DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'host/account/upgrade-baseline-0.4.0.json'


def validated_files(source, manifest):
    source, manifest = Path(source), Path(manifest)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('baseline must be an explicit regular source directory')
    spec = json.loads(manifest.read_text())
    if (spec.get('schema') != 1 or spec.get('app_id') != 'covin_account_admin'
            or spec.get('version') != '0.4.0' or not isinstance(spec.get('files'), dict)
            or not spec['files']):
        raise ValueError('invalid pinned 0.4.0 baseline manifest')
    app = source / APP_ROOT
    for path in (source / 'apps', app):
        if path.is_symlink() or not path.is_dir():
            raise ValueError('missing or linked baseline app directory')
    actual = set()
    for path in app.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('baseline contains links or special files')
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
    files = {}
    for relative, expected in spec['files'].items():
        path = PurePosixPath(relative)
        if (path.is_absolute() or '..' in path.parts or path.as_posix() != relative
                or not relative.startswith(APP_ROOT + '/')):
            raise ValueError('invalid baseline manifest path')
        if (not isinstance(expected, dict) or expected.get('mode') not in (0o644, 0o755)
                or not isinstance(expected.get('sha256'), str)):
            raise ValueError('invalid baseline manifest file entry')
        target = source / relative
        if relative not in actual:
            raise ValueError('baseline is missing a pinned source file')
        data = target.read_bytes()
        if (hashlib.sha256(data).hexdigest() != expected['sha256']
                or stat.S_IMODE(target.stat().st_mode) != expected['mode']):
            raise ValueError('baseline source or file mode differs from the pinned snapshot')
        files[relative] = (data, expected['mode'])
    if actual != set(spec['files']):
        raise ValueError('baseline contains unregistered app files')
    info = ET.fromstring(files[APP_ROOT + '/appinfo/info.xml'][0])
    if info.findtext('id') != 'covin_account_admin' or info.findtext('version') != '0.4.0':
        raise ValueError('baseline must contain app covin_account_admin version 0.4.0')
    if APP_ROOT + '/LICENSE' not in files:
        raise ValueError('baseline license notice is missing')
    return files


def copy_baseline(source, manifest, destination):
    # Validate every byte before creating any output. Copy those validated bytes,
    # rather than reading potentially changed source files a second time.
    files = validated_files(source, manifest)
    destination = Path(destination)
    if (destination.is_symlink() or not destination.is_dir()
            or any(destination.iterdir())):
        raise ValueError('baseline staging destination must be an empty regular directory')
    for relative, (data, mode) in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='external reference-0.4.0 directory')
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--copy-to', type=Path, help='empty isolated staging directory; optional')
    args = parser.parse_args()
    try:
        if args.copy_to is None:
            count = len(validated_files(args.source, args.manifest))
        else:
            count = copy_baseline(args.source, args.manifest, args.copy_to)
    except (ValueError, OSError, KeyError, ET.ParseError):
        print('STOP: external baseline failed pinned 0.4.0 source validation.', file=sys.stderr)
        return 1
    print(f'PASS: pinned 0.4.0 baseline ({count} app files).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
