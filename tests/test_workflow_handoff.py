from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_weekly_and_monthly_generators_explicitly_dispatch_publishers():
    for name in ('weekly-authority-support.yml', 'monthly-market-watch.yml'):
        workflow = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
        assert workflow['permissions']['actions'] == 'write'
        steps = next(iter(workflow['jobs'].values()))['steps']
        dispatch = [step for step in steps if 'gh workflow run publish-articles.yml' in step.get('run', '')]
        assert len(dispatch) == 1
        assert '-f chain_usa=true' in dispatch[0]['run']
        assert 'GH_TOKEN' in dispatch[0]['env']
