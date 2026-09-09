# ChronoTrace dashboard

Next.js + React + Tailwind. Reads `eval-results/incidents.json` and
`eval-results/results.json` directly from the repository — there is no service
and no network round-trip, so a demo cannot stall on a request.

```bash
cd ..
uv run chronotrace eval --arm C --cases all   # produces the JSON
cd ui && npm install && npm run dev           # http://localhost:3939
```

## Deploying it

`npm run build` emits a fully static site into `ui/out` — no Node server, so it
can sit on S3 behind CloudFront, on Amplify Hosting, or on any static host, and
a demo cannot stall on a request. Every route is already static or SSG.

```bash
cd ui && npm run build      # -> ui/out
```

**AWS Amplify Hosting** is the shortest path. Point it at the repository with
`ui` as the app root, `npm run build` as the build command and `out` as the
artifact directory:

```yaml
version: 1
applications:
  - appRoot: ui
    frontend:
      phases:
        preBuild: { commands: ["npm ci"] }
        build: { commands: ["npm run build"] }
      artifacts: { baseDirectory: out, files: ["**/*"] }
      cache: { paths: ["node_modules/**/*"] }
```

`prebuild` refreshes `public/incidents.json` from `../eval-results/` when a local
eval has been run, and otherwise builds from the committed snapshot — so a fresh
clone, and a CI build that has no model and no credentials, both work.

## Routes

| Route | Shows |
|---|---|
| `/` | Incident list — state, test, verification strength |
| `/incident/[id]` | The full report, in five sections |
| `/eval` | The three-arm comparison |

## Three states, made visible

Abstention is a UX feature here, not a caveat. Every incident is one of:

- **Fixed** — cause established, patch verified, regression guard created
- **Needs investigation** — race suspected, causal interleaving not proven
- **Abstained** — evidence points to a non-concurrency flake, no patch generated

## Conventions

- **No jargon in the interface.** "Suspiciousness", not Ochiai. "Adversarial
  schedules", not PCT. "Reproduced on demand", not Tier 1. The terms live in
  tooltips and the README.
- **The verification tier travels with every result**, worded so a weaker check
  cannot read as proof.
- **Colour never carries meaning alone.** Every state has an icon and a text
  label.
- **Motion carries information or it does not ship.** Spans stagger in the order
  they executed; rejected policy chips shake once. Nothing loops — an infinite
  animation reads as a loading state — and nothing runs longer than 500 ms.
  `prefers-reduced-motion` disables all of it.
