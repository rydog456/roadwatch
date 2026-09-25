# Roadwatch

Roadwatch is an iOS analyst dashboard for road-surface detections and nearby environmental hazards.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (workflow-assigned port)
- `pnpm --filter @workspace/roadwatch-mobile run dev` — run the Expo iOS app through its managed workflow
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec

Use the configured managed workflows rather than starting artifact dev commands directly. Environmental data uses public APIs and needs no API key.

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild
- Mobile: Expo Router and React Native

## Where things live

- `lib/api-spec/openapi.yaml` — environmental context API contract
- `artifacts/api-server/src/lib/environmental-context.ts` — NWS and USGS fetch, normalization, distance filtering
- `artifacts/api-server/src/routes/road-context.ts` — validated `/api/road-context` endpoint
- `artifacts/roadwatch-mobile/app/(tabs)/index.tsx` — analyst dashboard
- `artifacts/roadwatch-mobile/constants/colors.ts` — app palette
- `docs/roadwatch-data-plan.md` — proposed device fields, evidence-to-inspection workflow, and MVP boundary

## Architecture decisions

- Environmental reports are context, not proof of road damage or inputs that automatically override device-sensor priority.
- The API preserves each provider's availability/error state instead of treating outages as “no hazards.”
- NWS covers U.S. forecast points and active weather alerts; USGS supplies recent earthquake events. The server normalizes and briefly caches public responses.
- Focus the near-term product on repeatable pavement screening from existing vehicle routes (camera + IMU + GPS); LiDAR/thermal are optional, and structural/NDT claims require qualified follow-up. Inspection priority is a screening recommendation requiring human review, not a safety certification.

## Product

The dashboard displays a clearly labeled sample sensor-fusion detection and live NWS weather/alerts and nearby USGS earthquakes for selectable U.S. demonstration locations. GroundSignal in the supplied lean canvas is the broader venture concept; Roadwatch remains the road-focused app name unless the user chooses to rename it.

## User preferences

The car-mounted device will supply its own sensor readings and location. Its actual payload fields are still pending from the user.

## Gotchas

- Google Maps integration and a real road-severity heat map are pending a Google Maps SDK for iOS key. Never present a mock as live Google data.
- Update the OpenAPI spec and run codegen before changing typed API consumers.
- NWS requires an identifying User-Agent; do not remove it from server requests.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
