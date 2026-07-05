# Source map

Concrete file / folder index for the parts of the repo that matter to
agents. Items in `data-lakehouse/`, `donor-*`, `uml-p-screener/`, `vnpy/`,
`zhilian/`, `liepin/`, `qcc/`, `li_s_additives/`, `front/`, `reports/`,
`memory/`, `ditiediantu/` are intentionally omitted -- they are unrelated
side experiments and should not be touched when working on xiaohongshu-Loop.

## `xiaohongshu-saas/` (backend)

```
xiaohongshu-saas/
  app/
    main.py                 # FastAPI app factory + lifespan
    api/                    # HTTP routes
    core/                   # business services
    channels/
      base.py               # Channel protocol
      xiaohongshu/          # publisher, capture, commenter, selectors
      douyin/               # skeleton
    content_factory/        # prompt templates, LLM wrappers
    scheduler/              # APScheduler jobs + cron config
    workers/                # background tasks + SSE
    db/                     # session, engine, migrations
    models/                 # SQLAlchemy ORM
    schemas/                # pydantic models
  data/
    cookies/                # login cookies (git-ignored)
    images/                 # generated + uploaded images
    templates/              # Jinja templates for notes
  logs/                     # rotating logs
  scripts/                  # one-off operational scripts
  tests/
    unit/  integration/  e2e/  fixtures/
  requirements.txt
  pyproject.toml
```

## `web/` (frontend console)

```
web/
  src/
    pages/                  # route-level components
    components/             # reusable widgets
    hooks/                  # data + lifecycle hooks
    api/                    # REST client
    sse/                    # EventSource wrappers
    lib/                    # utilities
    __tests__/              # vitest specs
  public/                   # static assets
  index.html
  vite.config.ts
  package.json
```

## `packages/` (packaging)

```
packages/
  xhs-saas-console/         # electron + react console bundled
  installer/                # packaging glue
```

## `installer/`

```
installer/
  build.ps1                 # top-level build entrypoint
  make_msi.ps1              # MSI assembly (Advanced Installer / WiX)
  sign.ps1                  # code-sign helper
  resources/                # icons, license.rtf
  README.md                 # packaging notes
```

## `scripts/` (operational)

```
scripts/
  start_backend.ps1
  start_console.ps1
  start_frontend.ps1
  snipaste-ocr.{ps1,bat}    # captcha OCR helper
  backup_db.ps1
  fix_tests.sh / .ps1
```

## `docs/`

Hand-written project documentation. Not auto-generated.

```
docs/
  README.md
  architecture.md
  deployment.md
  changelog.md
  ...
```

## `.github/`

Templates and workflows.

```
.github/
  workflows/
    python-ci.yml
    msi-release.yml
  ISSUE_TEMPLATE/
  PULL_REQUEST_TEMPLATE.md
```

## `openwiki/`

This directory. Agent-oriented wiki.