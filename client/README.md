# SURAKSHA — Mine Safety Intelligence

Smart PPE Compliance Monitoring & Reporting System for Underground Coal Mines.

## Run locally

```bash
npm install
npm run dev
```

Then open the printed local URL (usually http://localhost:5173).

## Build for production

```bash
npm run build
npm run preview
```

`npm run build` outputs static files to `dist/` — deployable to any static host
(Vercel, Netlify, S3, nginx, etc). Routing uses `HashRouter`, so it works even
without server-side URL rewrite rules.

## Project structure

```
src/
  components/   CaveNav (SVG arch navigation), AppShell, CaveBackdrop, MobileNav, ui.jsx (shared primitives)
  data/         mockData.js (all mock records), types.js (JSDoc data-model contracts)
  services/     API clients and response adapters per domain
  pages/        one file per route (see below)
```

## Routes

```
/                  Home (cinematic entrance)
/login             Secure access
/dashboard         Command Center (overview)
/live              Live PPE Verification (working scan demo)
/ppe               PPE Compliance
/workers           Workers list
/workers/:id       Worker 360 profile
/attendance        Workforce presence
/alerts            Safety alerts
/reports           Safety reports
/insights          Safety insights (AI intelligence panel)
/devices           Device fleet (cameras / RFID / controllers)
/devices/sync      Offline sync & resilience
/audit             Audit log
/champions         Safety champions / recognition
/settings          Settings hub
/settings/ppe      Mandatory PPE configuration
/settings/users    User management / access control
```

## Notes on the design

- Cave contour navigation (`src/components/CaveNav.jsx`) is generated from a
  parametric SVG arch, not a static image — it scales cleanly and the nav
  items are positioned mathematically along the same curve as the drawn line.
- The underground backdrop (`CaveBackdrop.jsx`) is procedural SVG/gradient art,
  not a stock photo, so the visual identity stays original throughout.
- Operational pages now read from the FastAPI service under `/api/v1`; worker
  CRUD and PPE face enrollment also write through to the backend. The remaining
  UI-only areas (authentication/users and some demo presentation content) are
  kept separate until their database models and routes exist.
