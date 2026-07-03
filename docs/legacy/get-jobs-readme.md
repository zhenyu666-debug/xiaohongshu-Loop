# get-jobs ZhiLian Auto-Delivery

Spring Boot 3 + Playwright + React. Auto-open zhaopin.com, filter jobs by keyword/city/degree, click "立即投递" card by card.

> 让你少点几下投简历按钮，把找老婆的时间还给生活。

## Features

- ZhiLian auto-login via Playwright (QR code, cookies persisted)
- Keyword / city / salary / degree filter
- Card-by-card traversal with delivery
- Anti-modal / pop-up interception, "已投递" auto-skip
- Three-strategy chain: HoverCard / DetailPage / ApiDirect
- React web UI at `http://localhost:5173`
- Structured logging for delivery progress, stats, failure diagnosis

## Prerequisites

1. JDK 17+ and Node 18+ (for frontend)
2. Playwright Chromium:
   ```bash
   npx playwright install chromium
   ```
3. Clone and build:
   ```bash
   git clone https://github.com/zhenyu666-debug/-JAVA-.git
   cd -JAVA-
   ./gradlew bootJar
   ```

## Run

### Backend
```bash
java -jar build/libs/get-jobs.jar
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

## First Login

1. Start the backend. It will trigger a login window on first run.
2. In the Chromium window that pops up, scan QR with the ZhiLian app.
3. After successful login, cookies are saved to `target/zhilian-cookies.json` (gitignored).
4. Future restarts reuse the cookies - no QR prompt.

> No login state, cookies, or account info is uploaded to git.

## Configuration

- `src/main/resources/application.yml` - port, database, CORS, logging
- `frontend/src/config/` - keyword, city, degree defaults
- Web UI can edit and persist config to SQLite at `data/getjobs.db`

## Tech Stack

| Module | Stack |
|---|---|
| Backend | Spring Boot 3.2, JPA/Hibernate, SQLite |
| Browser | Playwright (Chromium) |
| Frontend | React + Vite |
| Anti-detection | custom stealth (`anti-detection.js`) |
| Delivery strategy | Ralph three-tier + forced modal cleanup |

## Privacy

- `.gitignore` excludes `target/`, `data/`, `*.db`, `*.log`, `.auth/`
- Cookies live only in local `target/zhilian-cookies.json`
- The repository contains NO account, password, phone, or cookies

## Disclaimer

For learning only. You bear all consequences (account ban, delivery failure, etc.) of using this tool. Please comply with zhaopin.com terms of service and applicable laws.

---

Trabajo / Work / Labor / 务工 / 打工 / 赚钱