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
from spec2lean.runtime import runtime_executable, runtime_name, run_session, session_command


@pytest.mark.parametrize("repetitions", [1, 20_000])
def test_opencode_prompt_uses_stdin_without_size_limits_or_quoting_changes(repetitions):
    prompt = '\nSpecification: λ "quoted" `literal` $value\n' * repetitions
    command = [sys.executable, "-c",
        "import json, sys; print(json.dumps({'args': sys.argv[1:], 'prompt': sys.stdin.read()}))",
        "run", "--pure", "--title", "test session", prompt]
    completed = run_session(command, run_command=subprocess.run,
        capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    received = json.loads(completed.stdout)
    assert received["args"] == ["run", "--pure", "--title", "test session"]
    assert received["prompt"] == prompt
    assert session_command(command, "<prompt>") == completed.args


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


@pytest.mark.parametrize("premature_completion", [False, True])
def test_rust_loop_drives_current_planner_validation(planner_database, tmp_path, monkeypatch, harness_binary, premature_completion):
    monkeypatch.setattr('spec2lean.planning.runner.runtime_executable', lambda: str(harness_binary))
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
        calls = [{{'name':'specdb_submit_plan', 'arguments_json':json.dumps({{}} if turn == 1 else {submission!r})}}]
        content = json.dumps({{'reply':'','tool_calls':calls}})
        if {premature_completion!r}:
            if turn == 2: content = '{{"reply":'
            if turn == 3: content = json.dumps({{'reply':'Submitted successfully and accepted.', 'tool_calls':[]}})
            if turn == 4:
                prompt = message['params']['arguments']['prompt']
                assert 'tools have not accepted a final submission' in prompt
                assert 'The previous task is finished' not in prompt
        result = {{'structuredContent':{{'threadId':'test-thread','content':content}}}}
    else: result = {{'protocolVersion':'2025-06-18','capabilities':{{}},'serverInfo':{{'name':'test','version':'1'}}}}
    print(json.dumps({{'jsonrpc':'2.0','id':message['id'],'result':result}}), flush=True)
''')
    provider.chmod(0o755)
    monkeypatch.setenv("SPEC2LEAN_CODEX", str(provider))
    monkeypatch.setenv("SPEC2LEAN_RUNTIME", "rust-harness")
    output = build_plan(planner_database, tmp_path / "plans", request, timeout_seconds=30)
    metadata = json.loads((output / "planner-run.json").read_text())
    assert metadata["planner"] == "rust-harness"
    assert len(metadata["command"]) == 1
    assert Path(metadata["command"][0]).name == "spec2lean-harness"
    transcript = json.loads(metadata["stdout"])["transcript"]
    assert transcript["steps"] == (4 if premature_completion else 2)
    assert 'specdb_submit_plan' in transcript['tools']
    assert len(transcript["exchanges"]) == transcript["steps"]
    assert '"accepted":false' in transcript["exchanges"][0]["toolResults"][0]["output"]
    if premature_completion:
        assert transcript["exchanges"][1]["assistant"]["responseError"]
        assert not transcript["exchanges"][2]["toolResults"]
        assert "not complete" in transcript["exchanges"][2]["feedback"]
        assert '"accepted":true' in transcript["exchanges"][3]["toolResults"][0]["output"]
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
    assert request['mcp_namespace'] == 'bounded'
    assert request['model'] == 'openai/gpt-5.6-sol'
    assert calls[0][1]['env']['SPEC2LEAN_RUNTIME'] == 'rust-harness'
    assert result.stdout == 'test'


def test_missing_codex_reports_rust_dependency_and_preserves_failure_artifact(
    planner_database, tmp_path, monkeypatch,
):
    monkeypatch.setenv("SPEC2LEAN_RUNTIME", "rust-harness")
    monkeypatch.setenv("SPEC2LEAN_CODEX", str(tmp_path / "missing-codex"))
    monkeypatch.setattr("spec2lean.planning.runner.runtime_executable",
                        lambda: "/unused/spec2lean-harness")
    request = PlanningRequest.exact("synthetic", "1.0", ["alpha.u32"])
    with pytest.raises(RuntimeError, match="Rust harness Planner") as caught:
        build_plan(planner_database, tmp_path / "plans", request, timeout_seconds=10)
    assert "SPEC2LEAN_CODEX" in str(caught.value)
    assert "OpenCode Planner" not in str(caught.value)
    metadata_path = next((tmp_path / "plans").rglob("planner-run.json"))
    metadata = json.loads(metadata_path.read_text())
    assert metadata["planner"] == "rust-harness"
    assert metadata["outcome"] == "FAILED"
    assert metadata["command"] == ["/unused/spec2lean-harness"]
    assert "Codex CLI" in metadata["error"]


def test_explicit_codex_path_works_without_codex_on_path(
    tmp_path, monkeypatch,
):
    executable = tmp_path / "spec2lean-harness"
    executable.write_text(f'''#!{sys.executable}
import os, sys
sys.stdin.read()
print(os.environ['SPEC2LEAN_CODEX'])
''')
    executable.chmod(0o755)
    config = {'default_agent': 'test', 'agent': {'test': {
        'model': 'openai/gpt-5.6-sol', 'variant': 'medium', 'steps': 1,
    }}, 'mcp': {'bounded': {'command': ['unused']}}}
    result = run_session([str(executable), 'prompt'], run_command=subprocess.run,
                         env={'PATH': '', 'SPEC2LEAN_CODEX': sys.executable,
                              'OPENCODE_CONFIG_CONTENT': json.dumps(config)},
                         timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == str(Path(sys.executable).resolve())


def test_rust_repair_preserves_context_gate_and_current_manifests(tmp_path, monkeypatch, harness_binary):
    monkeypatch.setattr('spec2lean.troubleshooting.opencode.runtime_executable', lambda: str(harness_binary))
    from test_troubleshooting import _run, _write_build_inputs, GROUP, REPAIRED_SOURCE, UNIT
    from spec2lean.troubleshooting.opencode import run_opencode_repair
    plan, roots, _, manifest = _write_build_inputs(tmp_path)
    submission = {'leanSource': REPAIRED_SOURCE, 'declarations': manifest['declarations'],
                  'changes': [{'description': 'Use explicit Nat.add for the compiler diagnostic.',
                               'affectedDeclarations': ['Spec2Lean.Repair.operation']}]}
    calls = [{'name': 'troubleshooting_get_context', 'arguments_json': json.dumps({'component': name})}
             for name in ('overview', 'leanSource', 'translationManifest', 'traceability')]
    calls.append({'name': 'troubleshooting_get_context', 'arguments_json': json.dumps({'component': 'semantics', 'unitId': UNIT['unitId']})})
    submit = {'name': 'troubleshooting_submit_repair', 'arguments_json': json.dumps(submission)}
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


def _recorded_codex(tmp_path, replies):
    """A provider double; the runtime, phase MCP, and validators remain real."""
    responses = tmp_path / 'provider-replies.json'
    responses.write_text(json.dumps(replies))
    requests = tmp_path / 'provider-requests.jsonl'
    provider = tmp_path / 'codex-recorded'
    provider.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
replies = json.loads(Path({str(responses)!r}).read_text())
turn = 0
for line in sys.stdin:
    message = json.loads(line)
    if 'id' not in message: continue
    if message['method'] == 'tools/call':
        with Path({str(requests)!r}).open('a') as log:
            log.write(json.dumps(message['params']) + '\\n')
        content = replies[min(turn, len(replies) - 1)]
        turn += 1
        print(json.dumps({{'jsonrpc':'2.0', 'method':'codex/event', 'params': {{
            '_meta': {{'requestId':message['id']}}, 'msg': {{'type':'token_count', 'info': {{
                'last_token_usage': {{'input_tokens':10, 'output_tokens':2, 'reasoning_output_tokens':1}}
            }}}}
        }}}}), flush=True)
        result = {{'structuredContent':{{'threadId':'recorded-thread', 'content':content}}}}
    else:
        result = {{'protocolVersion':'2025-06-18','capabilities':{{}},'serverInfo':{{'name':'test','version':'1'}}}}
    print(json.dumps({{'jsonrpc':'2.0','id':message['id'],'result':result}}), flush=True)
''')
    provider.chmod(0o755)
    return provider, requests


@pytest.mark.parametrize('failure', ['truncated', 'invalid_arguments', 'wrong_namespace'])
def test_rust_translation_recovers_without_partial_tool_execution(
    tmp_path, monkeypatch, harness_binary, failure,
):
    from test_translation import _write_inputs, _submission, GROUP
    from spec2lean.translation.runner import build_group_translation
    plan, _, _, semantics_root, _ = _write_inputs(tmp_path)
    submission = _submission()
    submission['leanSource'] += '\n-- Quotes " \\ tabs\t brackets {} and Unicode α\n' * 800
    call = {'name': 'translation_submit_translation', 'arguments': submission}
    valid = json.dumps({'reply': '', 'tool_calls': [call]})
    if failure == 'truncated':
        invalid = valid[:len(valid) // 2] + '\n```'
    elif failure == 'invalid_arguments':
        # Even a valid first call must not execute if a later call cannot decode.
        invalid = json.dumps({'reply': '', 'tool_calls': [call, {
            'name': call['name'], 'arguments_json': '{broken',
        }]})
    else:
        invalid = json.dumps({'reply': '', 'tool_calls': [{**call, 'name': 'other_submit_translation'}]})
    provider, requests_path = _recorded_codex(tmp_path, [invalid, valid])
    monkeypatch.setenv('SPEC2LEAN_RUNTIME', 'rust-harness')
    monkeypatch.setenv('SPEC2LEAN_CODEX', str(provider))
    monkeypatch.setattr('spec2lean.translation.runner.runtime_executable', lambda: str(harness_binary))
    output = build_group_translation(plan, semantics_root, tmp_path / 'translations', group=GROUP, timeout_seconds=30)
    assert (output / f'{GROUP}.lean').read_text() == submission['leanSource']
    metadata = json.loads((output / 'translator-run.json').read_text())
    transcript = json.loads(metadata['stdout'])['transcript']
    assert transcript['tools'] == ['translation_submit_translation']
    assert transcript['steps'] == 2 and transcript['outcome'] == 'SUBMITTED'
    first, second = transcript['exchanges']
    if failure == 'wrong_namespace':
        assert first['toolResults'][0]['output'] == 'unknown tool: other_submit_translation'
    else:
        assert first['toolResults'] == []
        assert first['assistant']['rawResponse'] == invalid
        assert first['assistant']['responseError']
    assert json.loads(second['toolResults'][0]['output'])['accepted'] is True
    assert transcript['usage']['inputTokens'] == 20
    assert transcript['usage']['outputTokens'] == 6
    requests = [json.loads(line) for line in requests_path.read_text().splitlines()]
    assert [request['name'] for request in requests] == ['codex', 'codex-reply']
    assert requests[1]['arguments']['threadId'] == 'recorded-thread'
    if failure != 'wrong_namespace':
        assert 'No tools were executed' in requests[1]['arguments']['prompt']


def test_rust_malformed_replies_stop_at_existing_step_limit(tmp_path, monkeypatch, harness_binary):
    from test_translation import _write_inputs, GROUP
    from spec2lean.translation.runner import build_group_translation
    plan, _, _, semantics_root, _ = _write_inputs(tmp_path)
    provider, requests_path = _recorded_codex(tmp_path, ['{"reply":"unfinished'])
    monkeypatch.setenv('SPEC2LEAN_RUNTIME', 'rust-harness')
    monkeypatch.setenv('SPEC2LEAN_CODEX', str(provider))
    monkeypatch.setattr('spec2lean.translation.runner.runtime_executable', lambda: str(harness_binary))
    with pytest.raises(RuntimeError, match='step'):
        build_group_translation(plan, semantics_root, tmp_path / 'translations', group=GROUP, timeout_seconds=30)
    metadata_path = next((tmp_path / 'translations').rglob('translator-run.json'))
    transcript = json.loads(json.loads(metadata_path.read_text())['stdout'])['transcript']
    assert transcript['steps'] == transcript['maxSteps'] == 40
    assert transcript['outcome'] == 'STEP_LIMIT'
    assert all(not exchange['toolResults'] for exchange in transcript['exchanges'])
    assert len(requests_path.read_text().splitlines()) == 40
    assert not list(metadata_path.parent.glob('*.lean'))
    assert transcript['usage']['inputTokens'] == 400
