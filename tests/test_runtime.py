from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec2lean.planning.models import PlanningRequest
from spec2lean.planning.runner import build_plan
from spec2lean.planning.scope import Phase1Query, ScopeResolver
from spec2lean.database import connect
from spec2lean.runtime import runtime_executable, runtime_name, run_session


@pytest.fixture
def harness_binary():
    path = Path(__file__).resolve().parents[1] / "harness/target/debug/spec2lean-harness"
    if not path.is_file():
        pytest.skip("build the Rust runtime before running bridge integration tests")
    return path


def test_runtime_selection_does_not_silently_fall_back(monkeypatch):
    monkeypatch.setenv("SPEC2LEAN_RUNTIME", "invalid")
    with pytest.raises(ValueError, match="SPEC2LEAN_RUNTIME"):
        runtime_name()
    monkeypatch.setenv("SPEC2LEAN_RUNTIME", "opencode")
    monkeypatch.setattr("spec2lean.runtime.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="OpenCode"):
        runtime_executable()


def test_rust_loop_drives_current_planner_validation(planner_database, tmp_path, monkeypatch, harness_binary):
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    with connect(planner_database, read_only=True) as connection:
        scope = ScopeResolver(connection).resolve(request).to_dict()
    submission = {
        "requestedUnitIds": scope["exactUnitIds"],
        "translationGroups": [{
            "name": "InstructionSemantics", "unitIds": scope["exactUnitIds"],
            "reason": "Source instruction family", "origin": "INFERRED",
            "supportingNodeIds": sorted({node for unit in scope["candidateUnits"]
                if unit["unitId"] in scope["exactUnitIds"] for node in unit["sourceNodeIds"]}),
        }],
        "externalPrerequisites": [], "dependencies": [],
    }
    # A provider double only: the Rust loop, stdio transport, Python scope tools,
    # rejected submission, accepted submission and published plan are all real.
    provider = tmp_path / "codex-double"
    provider.write_text(f'''#!{sys.executable}
import json, sys
turn = 0
for line in sys.stdin:
    message = json.loads(line)
    if 'id' not in message: continue
    if message['method'] == 'tools/call':
        turn += 1
        calls = [{{'name':'submit_plan', 'arguments_json':json.dumps({{}} if turn == 1 else {submission!r})}}]
        result = {{'structuredContent':{{'threadId':'test-thread','content':json.dumps({{'reply':'','tool_calls':calls}})}}}}
    else: result = {{'protocolVersion':'2025-06-18','capabilities':{{}},'serverInfo':{{'name':'test','version':'1'}}}}
    print(json.dumps({{'jsonrpc':'2.0','id':message['id'],'result':result}}), flush=True)
''')
    provider.chmod(0o755)
    monkeypatch.setenv("SPEC2LEAN_CODEX", str(provider))
    monkeypatch.setenv("SPEC2LEAN_RUNTIME", "rust-harness")
    output = build_plan(planner_database, tmp_path / "plans", request, timeout_seconds=30)
    metadata = json.loads((output / "planner-run.json").read_text())
    assert metadata["planner"] == "rust-harness"
    transcript = json.loads(metadata["stdout"])["transcript"]
    assert transcript["steps"] == 2
    assert len(transcript["exchanges"]) == 2
    assert '"accepted":false' in transcript["exchanges"][0]["toolResults"][0]["output"]
    assert [unit["unitId"] for unit in json.loads((output / "plan.json").read_text())["requestedUnits"]] == scope["exactUnitIds"]


def test_rust_timeout_stops_descendants(tmp_path):
    executable = tmp_path / "spec2lean-harness"
    pid_file = tmp_path / "child.pid"
    executable.write_text(f'''#!{sys.executable}
import subprocess, time
from pathlib import Path
child = subprocess.Popen([{sys.executable!r}, '-c', 'import time; time.sleep(60)'])
Path({str(pid_file)!r}).write_text(str(child.pid))
time.sleep(60)
''')
    executable.chmod(0o755)
    env = os.environ.copy()
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
        "default_agent": "test", "agent": {"test": {"model": "openai/test", "variant": "medium", "steps": 1}},
        "mcp": {"test": {"command": ["unused"]}},
    })
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_session([str(executable), "prompt"], run_command=subprocess.run, env=env, timeout=1)
    assert isinstance(caught.value.stdout, str) and isinstance(caught.value.stderr, str)
    pid = int(pid_file.read_text())
    stat = Path(f"/proc/{pid}/stat")
    try:
        assert stat.read_text().split()[2] == "Z"
    except FileNotFoundError:
        pass  # The child may be reaped between communicate() and this read.


def test_custom_runner_receives_rust_protocol_without_starting_a_process():
    calls = []
    def injected(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, 'test', '')
    config = {'default_agent': 'test', 'agent': {'test': {
        'model': 'openai/gpt-5.6-sol', 'variant': 'medium', 'steps': 3,
    }}, 'mcp': {'bounded': {'command': ['python', '-m', 'test'], 'timeout': 12000}}}
    result = run_session(['/missing/spec2lean-harness', 'unchanged phase prompt'],
                         run_command=injected, env={'OPENCODE_CONFIG_CONTENT': json.dumps(config)},
                         timeout=20, text=True, capture_output=True, check=False)
    request = json.loads(calls[0][1]['input'])
    assert request['prompt'] == 'unchanged phase prompt'
    assert request['mcp_command'] == ['python', '-m', 'test']
    assert request['model'] == 'openai/gpt-5.6-sol'
    assert calls[0][1]['env']['SPEC2LEAN_RUNTIME'] == 'rust-harness'
    assert result.stdout == 'test'


def test_rust_repair_preserves_context_gate_and_current_manifests(tmp_path, monkeypatch, harness_binary):
    from test_troubleshooting import _run, _write_build_inputs, GROUP, REPAIRED_SOURCE, UNIT
    from spec2lean.troubleshooting.opencode import run_opencode_repair
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    submission = {'leanSource': REPAIRED_SOURCE, 'declarations': manifest['declarations'],
                  'changes': [{'description': 'Use explicit Nat.add for the compiler diagnostic.',
                               'affectedDeclarations': ['Spec2Lean.Repair.operation']}]}
    calls = [{'name': 'get_context', 'arguments_json': json.dumps({'component': name})}
             for name in ('overview', 'leanSource', 'translationManifest', 'traceability')]
    calls.append({'name': 'get_context', 'arguments_json': json.dumps({'component': 'semantics', 'unitId': UNIT['unitId']})})
    submit = {'name': 'submit_repair', 'arguments_json': json.dumps(submission)}
    calls.append(submit)
    provider = tmp_path / 'codex-repair-double'
    provider.write_text(f'''#!{sys.executable}
import json, sys
turn = 0
for line in sys.stdin:
    message = json.loads(line)
    if 'id' not in message: continue
    if message['method'] == 'tools/call':
        turn += 1
        calls = {[submit]!r} if turn == 1 else {calls!r}
        result = {{'structuredContent':{{'threadId':'repair-thread','content':json.dumps({{'reply':'','tool_calls':calls}})}}}}
    else: result = {{'protocolVersion':'2025-06-18','capabilities':{{}},'serverInfo':{{'name':'test','version':'1'}}}}
    print(json.dumps({{'jsonrpc':'2.0','id':message['id'],'result':result}}), flush=True)
''')
    provider.chmod(0o755)
    monkeypatch.setenv('SPEC2LEAN_CODEX', str(provider))
    monkeypatch.setenv('SPEC2LEAN_RUNTIME', 'rust-harness')
    _, artifact = _run(plan, roots, run_opencode_repair)
    assert artifact['model']['provider'] == 'rust-harness'
    assert artifact['opencodeVersion'].startswith('spec2lean-harness')
    assert artifact['changedFiles']
    transcript = json.loads(artifact['session']['stdout'])['transcript']
    assert transcript['steps'] == 2
    assert '"accepted":false' in transcript['exchanges'][0]['toolResults'][0]['output']
    source = next(roots['translations'].rglob(f'{GROUP}.lean'))
    assert source.read_text() == REPAIRED_SOURCE
    published = json.loads(source.with_name('translation-manifest.json').read_text())
    assert published['declarations'] == manifest['declarations']
