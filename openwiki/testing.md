# Testing

## Layout

```
xiaohongshu-saas/tests/
  unit/                 # pure logic, no I/O
  integration/          # touches DB / fs, no network
  e2e/                  # drives Playwright against a live Xiaohongshu
  fixtures/             # golden responses, sample cookies (fake)
```

## Running

```powershell
# all unit + integration
cd xiaohongshu-saas
pytest -q

# only e2e (needs cookie)
pytest -q -m e2e --cookie=tests/fixtures/cookie.json

# coverage
pytest --cov=app --cov-report=term-missing
```

## Conventions

- One test file per module (`test_<module>.py`).
- Use `pytest.fixture` for shared setup; do NOT rely on global state.
- Mock the publisher in unit tests. The only place that should hit the
  real web flow is `e2e/`.
- Mark network-touching tests with `@pytest.mark.e2e`.

## Adding a test

1. Drop a fixture under `tests/fixtures/` if needed (anonymised).
2. Add a `test_*.py` mirroring the module name.
3. If you introduced a new schema, add a round-trip test that writes and
   reads it back.
4. Update `conftest.py` only when adding project-wide fixtures.

## Console / frontend tests

- Located under `web/src/**/__tests__/`.
- Vitest + React Testing Library.
- Run: `npm run test`.

## What to test before opening a PR

- `pytest -q` from the backend root is green.
- `npm run lint && npm run test` from `web/` is green.
- If you changed the publisher, run the e2e suite once with a real cookie.