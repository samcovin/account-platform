#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Sam Covin
"""Portable export candidate. No account deletion, disabling or recovery-key export."""
import argparse
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

NC = 'nextcloud-app'
MAIL = 'mailcowdockerized-dovecot-mailcow-1'
ROOT = Path('/opt/covin-account-exports')
HELPER = Path(__file__).resolve().with_name('nextcloud-export.php')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def relative_file(root, relative):
    p = Path(relative)
    if p.is_absolute() or not p.parts or '..' in p.parts:
        raise ValueError('Unsafe manifest path')
    target = root / p
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing or unsafe export file')
    return target

def inspect_mail(root):
    messages = []
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Unexpected mail symlink')
        if not p.is_file() or p.parent.name not in ('cur', 'new'):
            continue
        with p.open('rb') as stream:
            head = stream.read(16)
            stream.seek(0)
            if head.startswith((b'CRYPTED', b'\x1f\x8b', b'\x04\x22\x4d\x18')):
                raise ValueError('Mail export is not plaintext')
            message = BytesParser(policy=policy.default).parse(stream)
        if not message.keys() or any(part.defects for part in message.walk()):
            raise ValueError('Email parse check failed')
        messages.append(p)
    return messages

def mail_count(text):
    total = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.search(r' messages=(\d+) vsize=\d+\s*$', line)
        if not m:
            raise ValueError('Unexpected mailbox status format')
        total += int(m.group(1))
    return total

def recipient_readme():
    return """Account Export
====================

This package is a portable copy of information from your account.
Creating this package did not delete or change your account.

What is included
----------------
- files/: Your exported cloud files and folders.
- calendars/: Calendar files in .ics format. Most calendar apps can import them.
- contacts/: Contact files in .vcf format. Most contact apps can import them.
- mail/: Individual email messages in .eml format.
- nextcloud-report.json: Technical details about this export, including the
  original folder associated with each numbered email message.
- checksums.json: File sizes and SHA256 values used to verify the package.

Important limitations
---------------------
- This package does not include passwords, recovery codes, encryption keys,
  deleted items, file versions, shares, application databases or email rules.
- Shared calendars, calendar subscriptions and files outside your personal
  cloud storage are not included.
- Files protected with end-to-end encryption may not be readable.
- Restoring calendars, contacts and email requires importing them into a
  compatible application; this package does not include an automatic restore tool.

Keep the package and its password in a safe place. Reply to the delivery email
if you need help using it.
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    parser.add_argument('--include-shared-contacts', action='store_true',
                        help='Include all address books accessible to this user, separately labeled')
    args = parser.parse_args()
    if os.environ.get('ACCOUNT_PLATFORM_RUNTIME_REVIEWED') != '1':
        raise RuntimeError('review service targets and policy before setting ACCOUNT_PLATFORM_RUNTIME_REVIEWED=1')
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]', args.username):
        parser.error('Expected a service username of 2–64 lowercase safe characters')
    if os.geteuid() != 0:
        parser.error('Run with sudo')
    os.umask(0o077)
    if not HELPER.is_file():
        raise ValueError('PHP helper missing')
    if ROOT.is_symlink():
        raise ValueError('Export root must not be a symlink')
    ROOT.mkdir(mode=0o700, exist_ok=True)
    stat = ROOT.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o077:
        raise ValueError('Export root must be root-owned and mode 700')
    token = uuid.uuid4().hex
    work = ROOT / (args.username + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + token[:8])
    work.mkdir(mode=0o700)
    payload = work / 'payload'
    stage = '/tmp/covin-export-' + token
    created = []
    success = False
    log = (work / 'operator.log').open('ab')

    def run(command, *, output=None, capture=False):
        # Arguments are lists: user fields are never interpolated into shell code.
        result = subprocess.run(command, stdout=subprocess.PIPE if capture else (output or log), stderr=log)
        if result.returncode:
            raise RuntimeError('Command failed; inspect protected operator.log')
        return result.stdout.decode() if capture else None

    def dock(container, *arguments, user='root', capture=False, output=None):
        return run(['docker', 'exec', '-u', user, container, *arguments], capture=capture, output=output)

    try:
        print('Export directory:', work, flush=True)
        # Verify account existence before copying any data.
        dock(NC, 'php', 'occ', 'user:info', args.username, user='www-data')
        dock(MAIL, 'doveadm', 'user', args.username + '@example.test')
        for container, owner in ((NC, '33:33'), (MAIL, '5000:5000')):
            dock(container, 'mkdir', '-m', '700', stage)
            created.append(container)
            dock(container, 'chown', owner, stage)
        run(['docker', 'cp', str(HELPER), NC + ':' + stage + '/export.php'])
        dock(NC, 'chown', '33:33', stage + '/export.php')
        dock(NC, 'php', '-l', stage + '/export.php', user='www-data')
        dock(NC, 'mkdir', '-m', '700', stage + '/payload', user='www-data')
        print('Exporting Nextcloud files and address books…', flush=True)
        result = dock(NC, 'php', stage + '/export.php', args.username, stage + '/payload',
                      'yes' if args.include_shared_contacts else 'no', user='www-data', capture=True)
        if 'NEXTCLOUD_EXPORT_COMPLETE' not in result.splitlines():
            raise RuntimeError('Nextcloud export exited without completion marker')
        run(['docker', 'cp', NC + ':' + stage + '/payload', str(payload)])
        report = json.loads((payload / 'nextcloud-report.json').read_text())
        if report.get('complete') is not True or report.get('user') != args.username:
            raise ValueError('Invalid Nextcloud report')
        for item in report['files']:
            p = relative_file(payload / 'files', item['path'])
            if p.stat().st_size != item['bytes'] or digest(p) != item['sha256']:
                raise ValueError('File copy mismatch')
            with p.open('rb') as f:
                header = f.read(8192)
            if header.startswith(b'HBEGIN:') and b'oc_encryption_module' in header:
                raise ValueError('File still has a Nextcloud encryption header')

        print('Exporting owned calendars…', flush=True)
        for calendar in report['calendars']:
            if not re.fullmatch(r'[0-9]+', calendar['id']):
                raise ValueError('Unsafe calendar ID')
            path = payload / 'calendars' / ('calendar-' + calendar['id'] + '.ics')
            with path.open('xb') as f:
                dock(NC, 'php', 'occ', 'calendar:export', '--no-ansi', '--format=ical', '--',
                     args.username, calendar['uri'], user='www-data', output=f)
            # Run the installed parser on the file without placing contents in command arguments.
            run(['docker', 'cp', str(path), NC + ':' + stage + '/calendar.ics'])
            dock(NC, 'chown', '33:33', stage + '/calendar.ics')
            parsed = dock(NC, 'php', '-r',
                'require "/var/www/html/3rdparty/autoload.php"; '
                r'$x=\Sabre\VObject\Reader::read(file_get_contents($argv[1])); '
                'if($x->name!=="VCALENDAR")exit(1); echo "CALENDAR_PARSED";',
                stage + '/calendar.ics', user='www-data', capture=True)
            if parsed != 'CALENDAR_PARSED':
                raise ValueError('Calendar parser did not complete')
            calendar['file'] = str(path.relative_to(payload))

        print('Exporting readable mail…', flush=True)
        mailbox = args.username + '@example.test'
        before = dock(MAIL, 'doveadm', 'mailbox', 'status', '-u', mailbox, 'messages vsize', '*', capture=True)
        dock(MAIL, 'doveadm', '-o', 'plugin/mail_crypt_save_version=0', '-o', 'plugin/zlib_save=',
             '-o', 'maildir_copy_with_hardlinks=no', 'backup', '-u', mailbox, 'maildir:' + stage + '/Maildir')
        raw = work / 'maildir-private'
        run(['docker', 'cp', MAIL + ':' + stage + '/Maildir', str(raw)])
        messages = inspect_mail(raw)
        after = dock(MAIL, 'doveadm', 'mailbox', 'status', '-u', mailbox, 'messages vsize', '*', capture=True)
        if before != after or len(messages) != mail_count(before):
            raise ValueError('Mailbox changed or message counts differ; rerun into a new export')
        # Never deliver Dovecot attribute/key files or indexes. Only message bytes.
        mail = payload / 'mail'
        mail.mkdir(mode=0o700)
        mail_report = []
        for n, p in enumerate(messages, 1):
            name = f'message-{n:08d}.eml'
            shutil.copyfile(p, mail / name)
            if digest(p) != digest(mail / name):
                raise ValueError('Message copy mismatch')
            mail_report.append({'file': 'mail/' + name,
                                'maildir_folder': str(p.parent.parent.relative_to(raw)),
                                'maildir_filename': p.name})
        shutil.rmtree(raw)
        report['mail'] = mail_report
        report['limitations'] = [
            'Portable export only, not a recovery backup or account deletion authorization.',
            'No consistent cross-service snapshot; avoid edits during export.',
            'E2EE readable recovery is not established; ciphertext may be exported.',
            'Excluded: versions, trash, shares/ACLs, app databases, identities, credentials and encryption keys.',
            'Excluded: shared calendars, subscriptions and non-home file storage.',
            'Mail flags/folder restoration require manifest-aware tooling; no Sieve or mailbox configuration.',
            'Existing restore-test folders/collections are included; nothing is silently filtered by name.'
        ]
        report['status'] = 'exported-defined-scope-not-recovery-verified'
        (payload / 'nextcloud-report.json').write_text(json.dumps(report, indent=2) + '\n')
        (payload / 'README.txt').write_text(recipient_readme())
        hashes = []
        for p in sorted(payload.rglob('*')):
            if p.is_symlink():
                raise ValueError('Unexpected output symlink')
            if p.is_file():
                hashes.append({'path': str(p.relative_to(payload)), 'bytes': p.stat().st_size, 'sha256': digest(p)})
        (payload / 'checksums.json').write_text(json.dumps(hashes, indent=2) + '\n')
        for p in work.rglob('*'):
            if p.is_symlink():
                raise ValueError('Unexpected output symlink')
            os.chown(p, 0, 0)
            p.chmod(0o700 if p.is_dir() else 0o600)
        for item in hashes:
            if digest(relative_file(payload, item['path'])) != item['sha256']:
                raise ValueError('Final checksum mismatch')
        # Completion is written only after container cleanup succeeds.
        success = True
    finally:
        cleanup_failed = False
        for container in created:
            try:
                dock(container, 'rm', '-rf', '--', stage)
            except Exception:
                cleanup_failed = True
                print('Cleanup required in container:', container, 'path:', stage, file=sys.stderr)
        log.close()
        if cleanup_failed:
            raise RuntimeError('Staging cleanup incomplete; no completion marker issued')
    if success:
        (work / 'EXPORT_COMPLETE').write_text('Defined export scope verified; not a disaster recovery backup.\n')
        print('Files:', len(report['files']), 'Calendars:', len(report['calendars']), 'Messages:', len(report['mail']))
        print('Review payload/nextcloud-report.json for contact books, exclusions and limitations.')
        print('COVIN_ACCOUNT_EXPORT_COMPLETE')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP:', str(exc), file=sys.stderr)
        sys.exit(1)
