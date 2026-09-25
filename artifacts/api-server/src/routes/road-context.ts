import { Router, type IRouter } from "express";
import {
  GetRoadContextQueryParams,
  GetRoadContextResponse,
} from "@workspace/api-zod";
import {
  getEarthquakeContext,
  getWeatherContext,
} from "../lib/environmental-context";

const router: IRouter = Router();
const CACHE_TTL_MS = 2 * 60 * 1000;
const cache = new Map<string, { expiresAt: number; payload: unknown }>();

router.get("/road-context", async (req, res): Promise<void> => {
  const query = GetRoadContextQueryParams.safeParse(req.query);
  if (!query.success) {
    res.status(400).json({ error: "Valid latitude, longitude, and radiusMiles are required" });
    return;
  }

  const { latitude, longitude, radiusMiles } = query.data;
  const cacheKey = `${latitude},${longitude},${radiusMiles}`;
  const cached = cache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    res.json(cached.payload);
    return;
  }

  const location = { latitude, longitude };
  const [weather, earthquakes] = await Promise.all([
    getWeatherContext(location),
    getEarthquakeContext(location, radiusMiles),
  ]);
  const payload = GetRoadContextResponse.parse({
    generatedAt: new Date().toISOString(),
    location,
    radiusMiles,
    weather,
    earthquakes,
  });
  // Failed providers stay retryable rather than appearing as fresh data.
  if (weather.status !== "unavailable" || earthquakes.status !== "unavailable") {
    cache.set(cacheKey, { expiresAt: Date.now() + CACHE_TTL_MS, payload });
  }
  res.json(payload);
});

export default router;