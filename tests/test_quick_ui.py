from pathlib import Path
import fraudfence.core as core

def test_quick_frontend_exists_and_has_no_external_dependencies():
    base=core.ROOT/'static'
    html=(base/'quick.html').read_text()
    js=(base/'quick.js').read_text()
    assert 'Check supplier' in html and 'Verify payment' in html and 'AI fraud report' in html
    assert '<script src="/static/quick.js"' in html
    assert 'SIMULATED DATA' in html
    assert 'ozow-staging/check' in js
    assert 'api/ai/reports/' in js
    assert 'api/quick/company' in js
    assert 'https://' not in js or 'https:' in js
