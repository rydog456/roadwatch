import { useMemo, useState, type ReactNode } from 'react';
import { useGetRoadContext, getGetRoadContextQueryKey } from '@workspace/api-client-react';
import type { RoadContextResponse, WeatherAlert, EarthquakeEvent, ContextSourceState } from '@workspace/api-client-react';
import { Activity, AlertCircle, ArrowUpRight, Check, ChevronRight, Clock3, CloudSun, Compass, ExternalLink, MapPin, RefreshCw, Wind, Droplets, Radio, CircleDot, ShieldAlert } from 'lucide-react';

const CITIES = [
  { name: 'San Francisco', state: 'CA', latitude: 37.7749, longitude: -122.4194 },
  { name: 'Los Angeles', state: 'CA', latitude: 34.0522, longitude: -118.2437 },
  { name: 'Seattle', state: 'WA', latitude: 47.6062, longitude: -122.3321 },
  { name: 'Denver', state: 'CO', latitude: 39.7392, longitude: -104.9903 },
] as const;

function formatDate(value: string | null | undefined, options?: Intl.DateTimeFormatOptions) {
  if (!value) return 'Not provided';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not provided';
  return date.toLocaleString('en-US', options ?? { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
}

function Status({ state }: { state: ContextSourceState }) {
  return <span className={`status ${state}`} data-testid={`status-source-${state}`}><span className="live-dot" />{state}</span>;
}

function SourceError({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="source-error" role="status"><AlertCircle size={15} /><span>{message}</span></div>;
}

function SourceLink({ href, children, testId }: { href: string; children: ReactNode; testId: string }) {
  if (!/^https:\/\/[^ ]+$/i.test(href)) return <span className="source-link">Source link unavailable</span>;
  return <a className="source-link" href={href} target="_blank" rel="noopener noreferrer" data-testid={testId}>{children}<ArrowUpRight size={12} /></a>;
}

function WeatherPanel({ data }: { data: RoadContextResponse['weather'] }) {
  // Forecast and alerts are fetched independently. A forecast failure alone
  // does not make an empty, successfully fetched alert list uncertain.
  const alertsAvailable = data.status === 'available' || (data.status === 'partial' && !data.error?.includes('Alerts:'));
  const alerts = data.alerts ?? [];
  return (
    <article className="detail-panel" data-testid="panel-weather">
      <div className="panel-header">
        <div className="panel-title"><CloudSun size={19} strokeWidth={1.8} />Weather & alerts</div>
        <Status state={data.status} />
      </div>
      <div className="panel-body">
        <div className="panel-info"><span>PROVIDER</span><strong data-testid="text-weather-provider">{data.provider || 'National Weather Service'}</strong></div>
        <SourceError message={data.error} />
        <div className="alert-count"><strong>Active alerts</strong><span>{alertsAvailable ? `${alerts.length} RETURNED` : data.status === 'partial' ? 'PARTIAL RESULTS' : 'NO RESULT'}</span></div>
        {alerts.length > 0 ? (
          <div data-testid="list-weather-alerts">
            {alerts.map((alert: WeatherAlert) => (
              <div className="item" key={alert.id} data-testid={`item-alert-${alert.id}`}>
                <p className="item-title">{alert.event} <span className="severity">· {alert.severity}</span></p>
                <p className="item-sub">{alert.headline}</p>
                <div className="item-meta">
                  <span>{formatDate(alert.startsAt)} — {formatDate(alert.endsAt)}</span>
                  <SourceLink href={alert.sourceUrl} testId={`link-alert-${alert.id}`}>NWS alert</SourceLink>
                </div>
              </div>
            ))}
          </div>
        ) : alertsAvailable ? (
          <div className="empty" data-testid="empty-weather-alerts"><Check size={20} /><div><strong>No active NWS alerts returned</strong><p>For this location at the time of the latest update.</p></div></div>
        ) : (
          <div className="empty" data-testid="message-weather-incomplete"><AlertCircle size={20} /><div><strong>Alert information not confirmed</strong><p>{data.status === 'partial' ? 'Only part of the weather response is available.' : 'The weather source could not be reached.'} This does not mean there are no alerts.</p></div></div>
        )}
      </div>
    </article>
  );
}

function EarthquakePanel({ data }: { data: RoadContextResponse['earthquakes'] }) {
  const available = data.status === 'available';
  const events = data.events ?? [];
  return (
    <article className="detail-panel" data-testid="panel-earthquakes">
      <div className="panel-header">
        <div className="panel-title"><Activity size={19} strokeWidth={1.8} />Nearby earthquakes</div>
        <Status state={data.status} />
      </div>
      <div className="panel-body">
        <div className="panel-info"><span>PROVIDER</span><strong data-testid="text-earthquake-provider">{data.provider || 'U.S. Geological Survey'}</strong></div>
        <div className="panel-info" style={{ marginTop: 8 }}><span>SEARCH RADIUS</span><strong>{data.radiusMiles} miles</strong></div>
        <SourceError message={data.error} />
        <div className="alert-count"><strong>Recent events</strong><span>{available ? `${events.length} RETURNED` : data.status === 'partial' ? 'PARTIAL RESULTS' : 'NO RESULT'}</span></div>
        {events.length > 0 ? (
          <div data-testid="list-earthquakes">
            {events.map((event: EarthquakeEvent) => (
              <div className="item quake-row" key={event.id} data-testid={`item-earthquake-${event.id}`}>
                <div className="magnitude" aria-label={`Magnitude ${event.magnitude}`}>{event.magnitude.toFixed(1)}</div>
                <div>
                  <p className="item-title">{event.place}</p>
                  <p className="item-sub">{event.distanceMiles.toFixed(1)} mi from selected city · {event.depthKm.toFixed(1)} km deep</p>
                  <div className="item-meta"><span>{formatDate(event.occurredAt)}</span><SourceLink href={event.sourceUrl} testId={`link-earthquake-${event.id}`}>USGS event</SourceLink></div>
                </div>
              </div>
            ))}
          </div>
        ) : available ? (
          <div className="empty" data-testid="empty-earthquakes"><Check size={20} /><div><strong>No nearby events returned</strong><p>No USGS events in the latest {data.radiusMiles}-mile query.</p></div></div>
        ) : (
          <div className="empty" data-testid="message-earthquakes-incomplete"><AlertCircle size={20} /><div><strong>Event information not confirmed</strong><p>{data.status === 'partial' ? 'Only part of the earthquake response is available.' : 'The earthquake source could not be reached.'} This does not mean there were no events.</p></div></div>
        )}
      </div>
    </article>
  );
}

function LoadingDashboard() {
  return (
    <div className="fade-in" aria-label="Loading environmental context" data-testid="loading-context">
      <div className="hero-grid">
        <div className="condition-card"><div className="skeleton" style={{ width: 130, height: 13, opacity: .35 }} /><div><div className="skeleton" style={{ width: 180, height: 72, opacity: .35 }} /><div className="skeleton" style={{ width: 240, height: 23, marginTop: 12, opacity: .35 }} /></div><div className="skeleton" style={{ width: 290, height: 12, opacity: .35 }} /></div>
        <div className="context-card"><div className="skeleton" style={{ width: 130, height: 16 }} /><div className="skeleton" style={{ width: 85, height: 65, marginTop: 23 }} /><div className="skeleton" style={{ width: 180, height: 20, marginTop: 10 }} /></div>
      </div>
      <div className="section-head"><div className="skeleton" style={{ width: 220, height: 27 }} /></div>
      <div className="detail-grid"><div className="detail-panel" style={{ padding: 23, minHeight: 260 }}><div className="skeleton" style={{ width: '50%', height: 24 }} /><div className="skeleton" style={{ width: '85%', height: 12, marginTop: 45 }} /><div className="skeleton" style={{ width: '70%', height: 12, marginTop: 17 }} /></div><div className="detail-panel" style={{ padding: 23, minHeight: 260 }}><div className="skeleton" style={{ width: '48%', height: 24 }} /><div className="skeleton" style={{ width: '85%', height: 12, marginTop: 45 }} /><div className="skeleton" style={{ width: '70%', height: 12, marginTop: 17 }} /></div></div>
    </div>
  );
}

export default function Dashboard() {
  const [selected, setSelected] = useState(0);
  const city = CITIES[selected];
  const params = useMemo(() => ({ latitude: city.latitude, longitude: city.longitude, radiusMiles: 25 }), [city]);
  const { data, error, isPending, isFetching, isError, refetch } = useGetRoadContext(params, { query: { queryKey: getGetRoadContextQueryKey(params), staleTime: 60000, retry: 1 } });
  const errorText = error instanceof Error ? error.message : 'The context request did not complete.';
  const hasSnapshot = Boolean(data);
  return (
    <div className="app-shell">
      <aside className="rail">
        <a href="/" className="brand" data-testid="link-home" aria-label="Roadwatch home"><span className="brand-mark"><Compass size={21} strokeWidth={1.8} /></span><span><span className="brand-name">roadwatch<span style={{ color: 'var(--rw-pink)' }}>.</span></span><span className="brand-sub">Public works intelligence</span></span></a>
        <div className="rail-label">Workspace</div>
        <nav aria-label="Main navigation"><div className="rail-item active" aria-current="page"><CircleDot size={17} /><span>Context overview</span></div></nav>
        <div className="rail-bottom"><div className="eyebrow"><span className="live-dot" /> PUBLIC DATA LAYER</div><p>Environmental context for planning, not a road-condition detection system.</p></div>
      </aside>
      <main className="main">
        <header className="topbar"><div className="crumb"><span>Roadwatch Web</span><ChevronRight size={13} /><strong>Context overview</strong></div><div className="topbar-right"><span>Analyst workspace</span><div className="avatar" aria-hidden="true">RW</div></div></header>
        <div className="content">
          <div className="eyebrow"><span className="eyebrow-line" /> LIVE ENVIRONMENTAL CONTEXT / 01</div>
          <div className="page-heading"><div><h1>Context, <em>not conjecture.</em></h1><p>Current weather and seismic activity around the places your team watches. Source-reported data only; no road damage is inferred.</p></div><button className="refresh" type="button" disabled={isFetching} onClick={() => void refetch()} data-testid="button-refresh"><RefreshCw size={15} className={isFetching ? 'spinning' : ''} />{isFetching ? 'Refreshing…' : 'Refresh data'}</button></div>
          <div className="selector-row" role="group" aria-label="Select demo city"><span className="selector-label">Viewing area</span>{CITIES.map((item, i) => <button type="button" key={item.name} onClick={() => setSelected(i)} className={`city-button ${selected === i ? 'selected' : ''}`} aria-pressed={selected === i} data-testid={`button-city-${item.name.toLowerCase().replaceAll(' ', '-')}`}>{item.name}</button>)}</div>
          <div className="scope-line"><span><MapPin size={13} /> {city.name}, {city.state}</span><span><CircleDot size={13} /> 25-mile search radius</span><span>{city.latitude.toFixed(4)}° N, {Math.abs(city.longitude).toFixed(4)}° W</span>{data && <span data-testid="text-generated-at"><Clock3 size={13} /> Updated {formatDate(data.generatedAt)}</span>}</div>
          {isError && <div className="error-banner" role="alert" data-testid={hasSnapshot ? 'message-stale-error' : 'message-request-error'}><ShieldAlert size={20} style={{ flex: 'none' }} /><div><strong>{hasSnapshot ? 'Refresh failed — showing the last retrieved snapshot' : 'Context could not be loaded'}</strong><p>{errorText} {hasSnapshot ? `This snapshot was generated ${formatDate(data?.generatedAt)} and may be out of date.` : 'Source availability cannot be determined right now. Try again.'}</p></div><button type="button" onClick={() => void refetch()} data-testid="button-retry">Retry</button></div>}
          {isPending && !data ? <LoadingDashboard /> : data ? (
            <div className="fade-in" key={selected}>
              <div className="hero-grid">
                <section className="condition-card" aria-label="Current NWS forecast" data-testid="card-forecast">
                  <div className="card-kicker"><Radio size={14} /> NATIONAL WEATHER SERVICE <span className="source-state">{data.weather.status.toUpperCase()}</span></div>
                  <div>{data.weather.temperature !== null ? <><div className="condition-main"><span className="condition-temp" data-testid="text-temperature">{data.weather.temperature}°</span><span className="condition-unit">{data.weather.temperatureUnit || ''}</span></div><p className="condition-description" data-testid="text-forecast">{data.weather.shortForecast || 'Forecast description unavailable'}</p></> : <><h2 className="condition-unavailable">{data.weather.status === 'unavailable' ? 'Forecast unavailable' : 'Forecast incomplete'}</h2><p className="condition-help">NWS conditions could not be fully reported for this location. Check the source status below.</p></>}</div>
                  <div className="condition-meta"><span><Droplets size={15} /> {data.weather.precipitationProbability !== null ? `${data.weather.precipitationProbability}% precipitation` : 'Precipitation not reported'}</span><span><Wind size={15} /> {data.weather.windSpeed || 'Wind not reported'}</span></div>
                </section>
                <section className="context-card" aria-label="USGS nearby earthquake summary" data-testid="card-earthquake-summary">
                  <div className="context-top"><span className="context-overline">Within 25 miles</span><span className="context-icon"><Activity size={20} strokeWidth={1.8} /></span></div>
                   <div>{data.earthquakes.status === 'available' ? <div className="context-number" data-testid="text-earthquake-count">{data.earthquakes.events.length.toString().padStart(2, '0')}</div> : <div className="context-number">—</div>}<div className="context-title">{data.earthquakes.status === 'available' ? 'USGS events returned' : data.earthquakes.status === 'partial' ? 'Partial event data' : 'Events unavailable'}</div><p className="context-copy">{data.earthquakes.status === 'available' ? 'Recent earthquakes in the selected search area.' : 'The source could not confirm a complete event count.'}</p></div>
                  <div className="context-foot"><span className="live-dot" /> {data.earthquakes.provider || 'USGS'} · {data.earthquakes.status}</div>
                </section>
              </div>
              <div className="section-head"><div><h2>Source detail</h2><p>Read the original reports before taking action.</p></div><div className="aside">NWS + USGS / PUBLIC SOURCES</div></div>
              <div className="detail-grid"><WeatherPanel data={data.weather} /><EarthquakePanel data={data.earthquakes} /></div>
            </div>
          ) : !isError ? <LoadingDashboard /> : null}
          <footer className="footer"><p><strong>A note on interpretation.</strong> Weather alerts and nearby earthquakes are environmental context, not evidence of potholes, pavement failure, or any other road damage. Field verification is required for road conditions.</p><div className="footer-source"><a href="https://www.weather.gov/" target="_blank" rel="noopener noreferrer" data-testid="link-nws-source">NWS <ExternalLink size={10} style={{ display: 'inline' }} /></a><a href="https://earthquake.usgs.gov/" target="_blank" rel="noopener noreferrer" data-testid="link-usgs-source">USGS <ExternalLink size={10} style={{ display: 'inline' }} /></a></div></footer>
        </div>
      </main>
    </div>
  );
}