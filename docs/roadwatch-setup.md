# Roadwatch — TypeScript web, mobile, and API

Roadwatch is a separate pnpm workspace. Use Node.js 24 and pnpm 10. From the repository root:

```sh
pnpm install --frozen-lockfile
pnpm run typecheck
```

These commands check the Roadwatch workspace, not InfraPulse. `pnpm run build` also builds every artifact (including the component-preview sandbox) and requires workflow-provided environment variables such as `PORT`; do not interpret a missing-port error from a bare shell as a failed typecheck. The API, web, and Expo mobile apps have independent entry points:

| Service | Command in a local clone | Replit |
| --- | --- | --- |
| API | `pnpm --filter @workspace/api-server run dev` | Managed `artifacts/api-server: API Server` workflow |
| Web | `pnpm --filter @workspace/roadwatch-web run dev` | Managed `artifacts/roadwatch-web: web` workflow |
| Mobile | `pnpm --filter @workspace/roadwatch-mobile run dev` | Managed `artifacts/roadwatch-mobile: expo` workflow |

In Replit, **start the managed workflows**, not the commands above directly: they provide `PORT`, path routing, and Expo host settings. For a standalone clone, the app commands require equivalent port and base-path settings; use the Replit preview for the integrated three-service experience rather than assuming a local standalone command reproduces the proxy. The web app calls the Roadwatch API under `/api`. Live environmental context comes from NWS and USGS public APIs and needs no API key.

The mobile screen's example sensor-fusion detection is **illustrative**, not a live feed from InfraPulse or a vehicle. The web screen displays live environmental context only. Neither weather nor earthquakes prove road damage. See [data scope and future payload plan](roadwatch-data-plan.md); the device ingestion contract described there is not implemented.

The source of truth for the environmental API is `lib/api-spec/openapi.yaml`. After changing it, run `pnpm --filter @workspace/api-spec run codegen`, then `pnpm run typecheck`. Generated client hooks and Zod schemas are consumed by the apps and API. Keep their contract in sync. See `replit.md` for Replit-specific operating notes.