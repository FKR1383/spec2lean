#!/usr/bin/env python3
"""Verify a completed real run through main's GUI contracts and optional browser UI."""
from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path

from spec2lean.gui.repository import ArtifactRepository, ArtifactRoots
from spec2lean.gui.server import GuiServer


def verify(root: Path, indexes: Path | None, browser: bool, screenshot: Path | None) -> dict:
    # Artifact output may be isolated under tmp/, while official source files
    # remain under the actual repository. Keep the GUI's source-root guard.
    roots = replace(ArtifactRoots.at(root), repository=Path(__file__).resolve().parents[1])
    if indexes:
        roots = replace(roots, indexes=indexes.resolve())
    repository = ArtifactRepository(roots)
    runs = repository.list_runs()
    assert runs and all(run['status'] == 'COMPLETE' for run in runs), runs
    summary = {'root': str(root.resolve()), 'runs': [], 'browser': 'not requested'}
    for run in runs:
        run_id = run['runId']
        units = repository.list_units(run_id)
        assert units
        for unit in units:
            unit_id = unit['unitId']
            view = repository.get_unit(run_id, unit_id)
            assert view['lean']['available'] and not view['warnings'], view['warnings']
            check = view['checks']
            assert check['status'] == 'PASS'
            assert all(check[part]['status'] == 'PASS' for part in ('build', 'coverage', 'traceability'))
            linked = [d for d in view['lean']['declarations'] if d.get('claims')]
            assert linked
            for declaration in linked:
                trace = repository.get_trace(run_id, unit_id, declaration['declaration'])
                assert trace['claims']
                for claim in trace['claims']:
                    assert claim['evidence']
                    assert declaration['declaration'] in claim['declarations']
                    for evidence in claim['evidence']:
                        assert claim['claimId'] in evidence['usedByClaims']
                        assert declaration['declaration'] in evidence['implementedByDeclarations']
                        source = repository.get_evidence_source(run_id, unit_id, evidence['evidenceId'])
                        assert source['evidence']['exactText']
                        assert source['sourceNodes'] and all(not n.get('broken') for n in source['sourceNodes'])
                        assert any(n['sourceSpans'] for n in source['sourceNodes'])
                        assert source['preview']['type'] in ('pdf', 'html')
                        if source['preview']['type'] == 'pdf':
                            assert repository.render_pdf_preview(run_id, unit_id, evidence['evidenceId']).startswith(b'\x89PNG')
            summary['runs'].append({
                'runId': run_id, 'unitId': unit_id,
                'checks': {part: check[part]['status'] for part in ('build', 'coverage', 'traceability')},
                'declarations': len(view['lean']['declarations']), 'mappedDeclarations': len(linked),
                'claims': len(view['claims']), 'evidence': len(view['evidence']),
                'leanVersion': check['build']['leanVersion'],
            })
    server = GuiServer(('127.0.0.1', 0), repository, runs[0]['runId'])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        for run in summary['runs']:
            prefix = f"/api/runs/{urllib.parse.quote(run['runId'])}/units/{urllib.parse.quote(run['unitId'])}"
            for endpoint in ('', '/lean', '/semantics', '/checks'):
                with urllib.request.urlopen(base + prefix + endpoint, timeout=10) as response:
                    assert response.status == 200 and json.load(response)
        if browser:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                engine = playwright.chromium.launch(headless=True)
                page = engine.new_page(viewport={'width': 1600, 'height': 1000})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda response: errors.append(f'{response.status}: {response.url}')
                        if response.status >= 400 else None)
                page.goto(base)
                page.locator('[data-unit]').first.click()
                page.locator('.code-line.mapped').first.wait_for()
                page.locator('[data-declaration]').first.click()
                page.locator('[data-claim]').first.click()
                page.locator('[data-evidence]').first.click()
                page.locator('.source-block').wait_for()
                page.wait_for_load_state('networkidle')
                assert page.locator('.claim-card').count() > 0
                assert page.locator('.evidence-card').count() > 0
                if screenshot:
                    page.locator(".source-block").scroll_into_view_if_needed()
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot), full_page=True)
                page.locator('[data-tab="checks"]').click()
                for text in ('Build', 'Coverage', 'Traceability'):
                    assert page.get_by_text(text, exact=True).count() > 0
                page.locator('[data-tab="evidence"]').click()
                page.locator('[data-index-evidence]').first.click()
                page.locator('.source-block').wait_for()
                assert page.locator('[data-tab="lean"].active').count() == 1
                page.locator('[data-back-run]').click()
                page.locator('[data-unit]').first.wait_for()
                assert not errors, errors
                summary['browser'] = 'PASS: code → claim → evidence → source, reverse links, checks, navigation; no JS errors'
                engine.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    summary['guiApi'] = 'PASS'
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--indexes', type=Path)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.indexes, args.browser, args.screenshot), indent=2))


if __name__ == '__main__':
    main()
