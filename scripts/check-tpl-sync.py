#!/usr/bin/env python3
"""Fail if template.tpl's embedded server JS has drifted from template.js, or if
metadata.yaml's first version points at a template that is not ours.

GTM only ever runs the copy inside template.tpl. template.js exists so the code
is reviewable and diffable. A desynced pair is the standard way one of these
repos ships a fix that never reaches anybody.

The gallery does not read HEAD. It reads template.tpl at the first sha listed
under versions: in metadata.yaml. On 2026-09-02 that entry was an upstream stape
commit, so the reviewer read stape's template and rejected the submission over a
name that HEAD had not carried since 2026-08-24.
"""
import io
import re
import subprocess
import sys

tpl = io.open('template.tpl', encoding='utf-8').read()
js = io.open('template.js', encoding='utf-8').read()

m = re.search(r'^___SANDBOXED_JS_FOR_SERVER___\n(.*?)\n^___', tpl, re.S | re.M)
if not m:
    sys.exit('check-tpl-sync: no ___SANDBOXED_JS_FOR_SERVER___ section in template.tpl')

if m.group(1).strip() != js.strip():
    sys.exit(
        'check-tpl-sync: template.tpl embedded JS differs from template.js.\n'
        'Copy template.js into the ___SANDBOXED_JS_FOR_SERVER___ section and commit both.'
    )

for needed, where, label in (
    ('logToBigQuery', js, 'template.js'),
    ('access_bigquery', tpl, 'template.tpl'),
):
    if needed not in where:
        sys.exit(
            'check-tpl-sync: %s is missing from %s. '
            'The BigQuery logging this fork exists for is gone.' % (needed, label)
        )

meta = io.open('metadata.yaml', encoding='utf-8').read()
m = re.search(r'^versions:\s*\n\s*-\s*sha:\s*([0-9a-f]{7,40})', meta, re.M)
if not m:
    sys.exit('check-tpl-sync: no first version sha in metadata.yaml')
first = m.group(1)

if subprocess.call(['git', 'merge-base', '--is-ancestor', first, 'HEAD']) != 0:
    sys.exit(
        'check-tpl-sync: metadata.yaml lists %s first, which is not an ancestor of '
        'HEAD. The gallery reads that commit; it must be one of ours.\n'
        'If this fails in CI, the checkout needs fetch-depth: 0.' % first[:12]
    )

shown = subprocess.run(['git', 'show', '%s:template.tpl' % first],
                       stdout=subprocess.PIPE).stdout.decode('utf-8')
if '"id": "github.com_ROAS-Architects"' not in shown:
    sys.exit(
        'check-tpl-sync: template.tpl at %s does not carry our brand id. That is '
        'the commit the gallery reads.' % first[:12]
    )

print('check-tpl-sync: ok')
