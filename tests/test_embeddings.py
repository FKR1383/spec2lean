from __future__ import annotations

import json
from dataclasses import replace

import pytest

from spec2lean import embeddings
from spec2lean.cli import _dump_json, main
from spec2lean.database import connect
from spec2lean.evidence.query import EvidenceQuery
from spec2lean.planning.scope import Phase1Query


class Embedder:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] if 'Alpha' in text or 'independent first operation' in text else [0.0, 1.0]
                for text in texts]


@pytest.fixture
def embedded(planner_database, monkeypatch):
    monkeypatch.setattr(embeddings, '_load', lambda *args: Embedder())
    embeddings.build(planner_database, 'test-model', revision='immutable-test-revision')
    return planner_database


def test_semantic_build_preserves_current_index_and_provenance(planner_database, monkeypatch):
    with connect(planner_database, read_only=True) as connection:
        before = _dump_json(connection)
    monkeypatch.setattr(embeddings, '_load', lambda *args: Embedder())
    info = embeddings.build(planner_database, 'test-model', revision='r1')
    assert info['node_count'] > 0 and info['dim'] == 2
    with connect(planner_database, read_only=True) as connection:
        assert _dump_json(connection) == before
        query = Phase1Query(connection)
        assert query.search('independent first operation') == []
        with embeddings.retrieval_selection('semantic'):
            hits = EvidenceQuery(connection).search('independent first operation', limit=2)
        assert len(hits) == 2
        assert hits[0]['similarity'] == 1
        details = EvidenceQuery(connection).show(hits[0]['nodeId'])
        assert 'Alpha' in details['exactText']
        assert details['sourceSpans'] and details['document']['sha256']
        assert details['nodeId'] == hits[0]['nodeId']
        assert query.search('independent first operation') == []


def test_semantic_query_uses_recorded_model_revision(embedded, monkeypatch):
    requested = []
    monkeypatch.setattr(embeddings, '_load', lambda *args: requested.append(args) or Embedder())
    with connect(embedded, read_only=True) as connection:
        embeddings.search(connection, 'independent first operation')
    assert requested == [('test-model', 'immutable-test-revision')]


@pytest.mark.parametrize('fault', ['missing', 'stale', 'dimension', 'nan', 'norm', 'incomplete'])
def test_invalid_semantic_index_is_refused(embedded, fault):
    with connect(embedded) as connection:
        if fault == 'missing': connection.execute('DROP TABLE embedding_builds')
        elif fault == 'stale': connection.execute("UPDATE nodes SET raw_text = raw_text || ' changed'")
        elif fault == 'dimension': connection.execute('UPDATE embeddings SET vector=?', (embeddings.pack([1.]),))
        elif fault == 'nan': connection.execute('UPDATE embeddings SET vector=?', (embeddings.pack([float('nan'), 0.]),))
        elif fault == 'norm': connection.execute('UPDATE embeddings SET vector=?', (embeddings.pack([2., 0.]),))
        else: connection.execute('DELETE FROM embeddings WHERE node_id=(SELECT min(node_id) FROM embeddings)')
    with connect(embedded, read_only=True) as connection:
        with pytest.raises(ValueError): embeddings.search(connection, 'independent first operation')
        assert Phase1Query(connection).search('Alpha')  # lexical still works


@pytest.mark.parametrize('vectors', [[[1., 0.]], [[float('nan'), 0.]] * 100])
def test_failed_rebuild_retains_old_index(embedded, monkeypatch, vectors):
    with connect(embedded) as connection:
        before = [tuple(row) for row in connection.execute('SELECT * FROM embeddings ORDER BY node_id')]
        info = embeddings.metadata(connection)
    class Broken:
        def encode(self, texts, **kwargs): return vectors
    monkeypatch.setattr(embeddings, '_load', lambda *args: Broken())
    with pytest.raises(ValueError): embeddings.build(embedded, 'broken')
    with connect(embedded) as connection:
        assert embeddings.metadata(connection) == info
        assert [tuple(row) for row in connection.execute('SELECT * FROM embeddings ORDER BY node_id')] == before


def test_query_dimension_and_filters(embedded, monkeypatch):
    with connect(embedded) as connection:
        assert embeddings.search(connection, 'query', source_type='pdf') == []
        assert all(row['node_type'] == 'paragraph' for row in embeddings.search(connection, 'query', node_type='paragraph'))
        class WrongDimension:
            def encode(self, *args, **kwargs): return [[1.]]
        monkeypatch.setattr(embeddings, '_load', lambda *args: WrongDimension())
        with pytest.raises(ValueError, match='dimension'): embeddings.search(connection, 'query')


def test_cli_semantic_selection_and_lexical_default(embedded, capsys):
    args = ['index', 'search', '--database', str(embedded), '--query', 'independent first operation']
    assert main(args + ['--index-mode', 'semantic']) == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits[0]['node_id'].startswith('node:') and hits[0]['similarity'] == 1
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_dry_run_does_not_load_or_write_embeddings(planner_database, monkeypatch):
    monkeypatch.setattr(embeddings, '_load', lambda *args: pytest.fail('dry run loaded a model'))
    before = planner_database.read_bytes()
    assert embeddings.ensure(planner_database, dry_run=True) == {'disposition': 'WOULD_BUILD'}
    assert planner_database.read_bytes() == before


def test_pipeline_records_mode_and_refuses_cross_mode_resume(planner_database, tmp_path, monkeypatch):
    from test_pipeline import _options, _services
    from spec2lean.pipeline.runner import run_pipeline
    from spec2lean.planning.models import PlanningRequest
    monkeypatch.setattr(embeddings, '_load', lambda *args: Embedder())
    options = _options(tmp_path, planner_database, index_mode='semantic', until_phase='plan')
    calls = []
    services = _services(options, planner_database, calls)
    request = PlanningRequest.exact('synthetic', '1.0', ['alpha.u32'])
    _, manifest = run_pipeline(request, options, services=services)
    assert manifest['indexMode'] == 'semantic'
    assert manifest['phase1']['semanticIndex']['disposition'] == 'BUILT'
    assert calls == ['plan']
    with pytest.raises(ValueError, match='index mode'):
        run_pipeline(request, replace(options, index_mode='lexical', resume=manifest['pipelineRunId']), services=services)
    assert embeddings.index_mode() == 'lexical'


def test_semantic_plan_is_not_reused_as_lexical(planner_database, tmp_path, monkeypatch):
    from test_pipeline import _options, _services
    from spec2lean.pipeline.runner import run_pipeline
    from spec2lean.planning.models import PlanningRequest
    monkeypatch.setattr(embeddings, '_load', lambda *args: Embedder())
    options = _options(tmp_path, planner_database, until_phase='plan')
    calls = []
    services = _services(options, planner_database, calls)
    request = PlanningRequest.exact('synthetic', '1.0', ['alpha.u32'])
    run_pipeline(request, options, services=services)
    calls.clear()
    run_pipeline(request, replace(options, index_mode='semantic'), services=services)
    assert calls == ['plan']


def test_latest_resume_selects_the_latest_matching_mode(tmp_path):
    from spec2lean.pipeline.runner import _latest_compatible_run
    from spec2lean.planning.models import PlanningRequest
    request = PlanningRequest.exact('synthetic', '1.0', ['alpha.u32'])
    for mode, updated in [('lexical', '2026-01-01'), ('semantic', '2026-01-02')]:
        path = tmp_path / 'synthetic/1.0' / f'pipeline-run:{mode}' / 'run.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'request': request.to_dict(), 'updatedAt': updated,
                                    'indexMode': mode, 'pipelineRunId': f'pipeline-run:{mode}'}))
    assert _latest_compatible_run(tmp_path, request) == 'pipeline-run:lexical'
    assert _latest_compatible_run(tmp_path, request, 'semantic') == 'pipeline-run:semantic'
