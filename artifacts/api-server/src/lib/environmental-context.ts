type JsonObject = Record<string, unknown>;

export type Location = { latitude: number; longitude: number };

export type WeatherAlert = {
  id: string;
  event: string;
  headline: string;
  severity: string;
  startsAt: string | null;
  endsAt: string | null;
  sourceUrl: string;
};

export type WeatherContext = {
  provider: string;
  status: "available" | "partial" | "unavailable";
  temperature: number | null;
  temperatureUnit: string | null;
  shortForecast: string | null;
  precipitationProbability: number | null;
  windSpeed: string | null;
  observedAt: string | null;
  alerts: WeatherAlert[];
  error: string | null;
};

export type EarthquakeEvent = {
  id: string;
  magnitude: number;
  place: string;
  occurredAt: string;
  depthKm: number;
  distanceMiles: number;
  sourceUrl: string;
};

export type EarthquakeContext = {
  provider: string;
  status: "available" | "partial" | "unavailable";
  radiusMiles: number;
  events: EarthquakeEvent[];
  error: string | null;
};

const USGS_FEED =
  "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/1.0_day.geojson";
const NWS_BASE = "https://api.weather.gov";
const REQUEST_TIMEOUT_MS = 10_000;
const USER_AGENT = "Roadwatch/1.0 (road-infrastructure research prototype)";

function object(value: unknown): JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isoDate(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Date(value).toISOString();
  }
  if (typeof value === "string" && !Number.isNaN(Date.parse(value))) {
    return new Date(value).toISOString();
  }
  return null;
}

function sourceError(error: unknown): string {
  return error instanceof Error ? error.message : "Source unavailable";
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, {
    headers: {
      Accept: "application/geo+json, application/json",
      "User-Agent": USER_AGENT,
    },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from ${new URL(url).hostname}`);
  }
  return response.json();
}

function nwsUrl(value: unknown): string {
  const raw = text(value);
  if (!raw) throw new Error("Forecast location was not provided by NWS");
  const url = new URL(raw);
  if (url.protocol !== "https:" || url.hostname !== "api.weather.gov") {
    throw new Error("NWS returned an unexpected forecast location");
  }
  return url.toString();
}

export async function getWeatherContext({
  latitude,
  longitude,
}: Location): Promise<WeatherContext> {
  const weather: WeatherContext = {
    provider: "National Weather Service",
    status: "unavailable",
    temperature: null,
    temperatureUnit: null,
    shortForecast: null,
    precipitationProbability: null,
    windSpeed: null,
    observedAt: null,
    alerts: [],
    error: null,
  };

  const errors: string[] = [];
  const point = `${latitude.toFixed(4)},${longitude.toFixed(4)}`;
  const [pointsResult, alertsResult] = await Promise.allSettled([
    fetchJson(`${NWS_BASE}/points/${point}`),
    fetchJson(`${NWS_BASE}/alerts/active?point=${point}`),
  ]);

  if (pointsResult.status === "fulfilled") {
    try {
      const points = object(object(pointsResult.value).properties);
      const forecast = await fetchJson(nwsUrl(points.forecastHourly));
      const periods = list(object(object(forecast).properties).periods);
      if (periods.length === 0) throw new Error("NWS returned no hourly forecast");
      const firstPeriod = object(periods[0]);
      weather.temperature = number(firstPeriod.temperature);
      weather.temperatureUnit = text(firstPeriod.temperatureUnit);
      weather.shortForecast = text(firstPeriod.shortForecast);
      weather.windSpeed = text(firstPeriod.windSpeed);
      const precipitation = number(
        object(firstPeriod.probabilityOfPrecipitation).value,
      );
      weather.precipitationProbability =
        precipitation === null ? null : Math.round(precipitation);
      // NWS hourly periods are forecasts, not observations. Do not claim
      // an observation time for a forecast value.
      weather.status = "available";
    } catch (error) {
      errors.push(`Forecast: ${sourceError(error)}`);
    }
  } else {
    errors.push(`Forecast: ${sourceError(pointsResult.reason)}`);
  }

  if (alertsResult.status === "fulfilled") {
    weather.alerts = list(object(alertsResult.value).features)
      .map((feature): WeatherAlert | null => {
        const item = object(feature);
        const properties = object(item.properties);
        const id = text(item.id) ?? text(properties.id);
        const event = text(properties.event);
        if (!id || !event) return null;
        return {
          id,
          event,
          headline: text(properties.headline) ?? event,
          severity: text(properties.severity) ?? "Unknown",
          startsAt: isoDate(properties.onset ?? properties.effective),
          endsAt: isoDate(properties.ends ?? properties.expires),
          sourceUrl:
            text(properties["@id"]) ??
            (id.startsWith("https://") ? id : "https://www.weather.gov/alerts"),
        };
      })
      .filter((alert): alert is WeatherAlert => alert !== null)
      .slice(0, 12);
    weather.status = weather.status === "available" ? "available" : "partial";
  } else {
    errors.push(`Alerts: ${sourceError(alertsResult.reason)}`);
    if (weather.status === "available") weather.status = "partial";
  }

  if (errors.length > 0) weather.error = errors.join("; ");
  return weather;
}

function distanceMiles(first: Location, second: Location): number {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const deltaLat = toRadians(second.latitude - first.latitude);
  const deltaLon = toRadians(second.longitude - first.longitude);
  const latA = toRadians(first.latitude);
  const latB = toRadians(second.latitude);
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(latA) * Math.cos(latB) * Math.sin(deltaLon / 2) ** 2;
  return 2 * 3958.8 * Math.asin(Math.sqrt(a));
}

export async function getEarthquakeContext(
  location: Location,
  radiusMiles: number,
): Promise<EarthquakeContext> {
  const earthquakes: EarthquakeContext = {
    provider: "USGS Earthquake Hazards Program",
    status: "unavailable",
    radiusMiles,
    events: [],
    error: null,
  };

  try {
    const feed = await fetchJson(USGS_FEED);
    earthquakes.events = list(object(feed).features)
      .map((feature): EarthquakeEvent | null => {
        const item = object(feature);
        const properties = object(item.properties);
        const coordinates = list(object(item.geometry).coordinates);
        const longitude = number(coordinates[0]);
        const latitude = number(coordinates[1]);
        const magnitude = number(properties.mag);
        const occurredAt = isoDate(properties.time);
        const id = text(item.id);
        if (
          latitude === null ||
          longitude === null ||
          magnitude === null ||
          occurredAt === null ||
          id === null
        ) {
          return null;
        }
        const distance = distanceMiles(location, { latitude, longitude });
        if (distance > radiusMiles) return null;
        return {
          id,
          magnitude,
          place: text(properties.place) ?? "Location not specified",
          occurredAt,
          depthKm: number(coordinates[2]) ?? 0,
          distanceMiles: Math.round(distance * 10) / 10,
          sourceUrl: text(properties.url) ?? `${USGS_FEED}`,
        };
      })
      .filter((event): event is EarthquakeEvent => event !== null)
      .sort((a, b) => a.distanceMiles - b.distanceMiles)
      .slice(0, 12);
    earthquakes.status = "available";
  } catch (error) {
    earthquakes.error = sourceError(error);
  }

  return earthquakes;
}