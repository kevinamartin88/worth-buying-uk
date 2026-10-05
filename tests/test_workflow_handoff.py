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


def test_chart_commits_happen_before_publication_state_changes():
    for name in ('publish-articles.yml', 'publish-articles-us.yml'):
        workflow = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
        steps = next(iter(workflow['jobs'].values()))['steps']
        charts = next(i for i, step in enumerate(steps) if step['name'] == 'Prepare observed price-history charts')
        publish = next(i for i, step in enumerate(steps) if step.get('run') in ('python publish_articles.py', 'python publish_articles_us.py'))
        assert charts < publish
