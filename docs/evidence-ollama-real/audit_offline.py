"""Run with installed AgentEval 0.5.0 wheel. No HTTP, database or inference."""
import json
from pathlib import Path
from unittest.mock import patch
from agenteval.integrity import restore
from agenteval.comparison import compare_runs

folder = Path(__file__).resolve().parent
restored = []
with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
    for name in ('real-snapshot.json', 'replay-a.json', 'replay-b.json'):
        text = (folder / name).read_text(encoding='utf-8')
        data = json.loads(text)
        run = restore(text, data['id'], data['created_utc'])
        assert run.model_dump(mode='json') == data
        restored.append(run)
    assert restored[0].provenance == 'local_ollama'
    assert restored[0].metrics.passed == 0 and restored[0].metrics.failed == 3
    comparison = compare_runs(restored[1], restored[2])
    assert comparison.model_dump(mode='json') == json.loads((folder / 'replay-comparison.json').read_text())
    assert not compare_runs(restored[1], restored[0]).compatible
print('Three snapshots restored from RAW, hashes/checks verified, replay A/B reproduced offline. EXIT_CODE=0')
