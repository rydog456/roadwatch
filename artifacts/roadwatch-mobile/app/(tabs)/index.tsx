import { useState } from 'react';
import { Alert, Linking, Platform, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { getGetRoadContextQueryKey, useGetRoadContext } from '@workspace/api-client-react';
import type { EarthquakeEvent, WeatherAlert } from '@workspace/api-client-react';
import { useColors } from '@/hooks/useColors';
import colors from '@/constants/colors';

const C = colors.light;
const MONO = Platform.OS === 'ios' ? 'Menlo' : 'monospace';
const LOCATIONS = [
  { name: 'San Francisco', state: 'CA', latitude: 37.7749, longitude: -122.4194 },
  { name: 'Los Angeles', state: 'CA', latitude: 34.0522, longitude: -118.2437 },
  { name: 'Seattle', state: 'WA', latitude: 47.6062, longitude: -122.3321 },
  { name: 'Denver', state: 'CO', latitude: 39.7392, longitude: -104.9903 },
] as const;
const RADIUS_MILES = 25;

function formatTime(value: string | null | undefined) {
  if (!value) return 'Time not reported';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Time not reported';
  return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function openSource(url: string) {
  if (!/^https:\/\/[^ ]+$/i.test(url)) {
    Alert.alert('Source unavailable', 'No valid source link was provided.');
    return;
  }
  Linking.openURL(url).catch(() => Alert.alert('Could not open source', 'Please try again later.'));
}

function Label({ children, light = false }: { children: string; light?: boolean }) {
  return <Text style={[styles.label, light && styles.labelLight]}>{children}</Text>;
}

function SourceStatus({ status }: { status: string }) {
  const unavailable = status === 'unavailable';
  const partial = status === 'partial';
  return (
    <View style={[styles.sourceStatus, unavailable ? styles.statusUnavailable : partial ? styles.statusPartial : styles.statusAvailable]}>
      <View style={[styles.statusDot, { backgroundColor: unavailable ? C.destructive : partial ? C.signal : C.success }]} />
      <Text style={[styles.sourceStatusText, { color: unavailable ? C.destructive : partial ? '#98623F' : C.success }]}>
        {unavailable ? 'UNAVAILABLE' : partial ? 'PARTIAL' : 'LIVE'}
      </Text>
    </View>
  );
}

function SectionHeading({ index, title, meta }: { index: string; title: string; meta?: string }) {
  return (
    <View style={styles.sectionHeading}>
      <View style={styles.sectionNumber}><Text style={styles.sectionNumberText}>{index}</Text></View>
      <Text style={styles.sectionTitle}>{title}</Text>
      {!!meta && <Text style={styles.sectionMeta}>{meta}</Text>}
    </View>
  );
}

function Metric({ icon, label, value, unit, detail }: { icon: keyof typeof Feather.glyphMap; label: string; value: string; unit?: string; detail: string }) {
  return (
    <View style={styles.metric}>
      <View style={styles.metricTop}><Feather name={icon} size={15} color={C.mutedForeground} /><Text style={styles.metricLabel}>{label}</Text></View>
      <View style={styles.metricValueRow}><Text style={styles.metricValue}>{value}</Text>{unit && <Text style={styles.metricUnit}>{unit}</Text>}</View>
      <Text style={styles.metricDetail}>{detail}</Text>
    </View>
  );
}

function Skeleton() {
  return (
    <View style={styles.skeletonCard}>
      <View style={[styles.skeleton, { width: '44%', height: 12 }]} />
      <View style={[styles.skeleton, { width: '68%', height: 29, marginTop: 21 }]} />
      <View style={[styles.skeleton, { width: '85%', height: 11, marginTop: 20 }]} />
      <View style={[styles.skeleton, { width: '57%', height: 11, marginTop: 11 }]} />
    </View>
  );
}

function SourceLink({ label, url }: { label: string; url: string }) {
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`Open source: ${label}`}
      testID={`source-${label}`}
      onPress={() => openSource(url)}
      style={({ pressed }) => [styles.sourceLink, pressed && styles.pressed]}
    >
      <Text style={styles.sourceLinkText} numberOfLines={2}>{label}</Text>
      <Feather name="external-link" size={15} color={C.primary} />
    </Pressable>
  );
}

function AlertRow({ alert }: { alert: WeatherAlert }) {
  return (
    <View style={styles.alertRow}>
      <View style={styles.alertIcon}><Feather name="alert-triangle" size={17} color={C.destructive} /></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.alertEvent}>{alert.event}</Text>
        <Text style={styles.alertHeadline}>{alert.headline}</Text>
        <Text style={styles.alertMeta}>{alert.severity}{alert.endsAt ? ` · Until ${formatTime(alert.endsAt)}` : ''}</Text>
        <SourceLink label="View NWS alert" url={alert.sourceUrl} />
      </View>
    </View>
  );
}

function QuakeRow({ event }: { event: EarthquakeEvent }) {
  return (
    <View style={styles.quakeRow}>
      <View style={styles.magnitude}><Text style={styles.magnitudeText}>{event.magnitude.toFixed(1)}</Text><Text style={styles.magnitudeLabel}>MAG</Text></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.quakePlace}>{event.place}</Text>
        <Text style={styles.quakeDetail}>{event.distanceMiles.toFixed(1)} mi away · {event.depthKm.toFixed(1)} km deep</Text>
        <Text style={styles.quakeDetail}>{formatTime(event.occurredAt)}</Text>
        <SourceLink label="View USGS event" url={event.sourceUrl} />
      </View>
    </View>
  );
}

export default function DashboardScreen() {
  const insets = useSafeAreaInsets();
  const theme = useColors();
  const [locationIndex, setLocationIndex] = useState(0);
  const location = LOCATIONS[locationIndex];
  const params = { latitude: location.latitude, longitude: location.longitude, radiusMiles: RADIUS_MILES };
  const { data, isPending, isError, isFetching, refetch } = useGetRoadContext(params, {
    query: { queryKey: getGetRoadContextQueryKey(params), staleTime: 60_000, retry: 1 },
  });
  const weather = data?.weather;
  const earthquakes = data?.earthquakes;
  const refresh = () => { void refetch(); };

  return (
    <View style={[styles.screen, { backgroundColor: theme.background }]}>
      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingTop: Platform.OS === 'web' ? Math.max(insets.top, 67) + 14 : insets.top + 14, paddingBottom: Math.max(insets.bottom, Platform.OS === 'web' ? 34 : 20) + 32 }]}
        refreshControl={<RefreshControl refreshing={isFetching && !isPending} onRefresh={refresh} tintColor={C.primary} colors={[C.primary]} />}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.content}>
          <View style={styles.masthead}>
            <View style={styles.brandRow}>
              <View style={styles.brandMark}><View style={styles.brandMarkLine} /><View style={styles.brandMarkLineShort} /></View>
              <Text style={styles.brand}>ROADWATCH</Text>
              <Text style={styles.edition}>FIELD / 01</Text>
            </View>
            <View style={styles.headerRule} />
            <View style={styles.heroTop}><Text style={styles.eyebrow}>PUBLIC WORKS INTELLIGENCE</Text><Text style={styles.heroIndex}>RW—01</Text></View>
            <Text style={styles.heroTitle}>Road condition{'\n'}at a glance.</Text>
            <Text style={styles.heroSubtitle}>A clear view of sample sensor evidence and live environmental context.</Text>
            <View style={styles.heroFooter}><View style={styles.heroFooterDot} /><Text style={styles.heroFooterText}>ANALYST COCKPIT</Text><Text style={styles.heroFooterRight}>DEMONSTRATION VIEW</Text></View>
          </View>

          <View style={styles.locationBlock}>
            <View style={styles.locationTitleRow}>
              <View><Label>CONTEXT LOCATION · DEMO</Label><Text style={styles.locationName}>{location.name}<Text style={styles.locationState}>, {location.state}</Text></Text></View>
              <Feather name="crosshair" size={21} color={C.primary} />
            </View>
            <Text style={styles.coordinate}>{location.latitude.toFixed(4)}° N  /  {Math.abs(location.longitude).toFixed(4)}° W  ·  {RADIUS_MILES} MI RADIUS</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.locationChoices}>
              {LOCATIONS.map((item, index) => (
                <Pressable
                  key={item.name}
                  testID={`location-${item.name}`}
                  accessibilityRole="button"
                  accessibilityState={{ selected: index === locationIndex }}
                  onPress={() => setLocationIndex(index)}
                  style={({ pressed }) => [styles.locationChip, index === locationIndex && styles.locationChipSelected, pressed && styles.pressed]}
                >
                  <Text style={[styles.locationChipText, index === locationIndex && styles.locationChipTextSelected]}>{item.name}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>

          <SectionHeading index="01" title="Detection evidence" meta="SAMPLE" />
          <View style={styles.evidenceCard}>
            <View style={styles.evidenceTop}>
              <View style={styles.demoTag}><View style={styles.demoDot} /><Text style={styles.demoTagText}>DEMO DATA · NOT LIVE DEVICE INPUT</Text></View>
              <View style={styles.priority}><Text style={styles.priorityText}>HIGH PRIORITY</Text></View>
            </View>
            <View style={styles.defectHeading}><View style={styles.defectGlyph}><Feather name="activity" size={22} color={C.signal} /></View><View style={{ flex: 1 }}><Text style={styles.defectKicker}>SAMPLE FUSION DETECTION / 001</Text><Text style={styles.defectTitle}>Pothole</Text></View></View>
            <View style={styles.confidenceRow}><View><Label light>VISION CONFIDENCE</Label><Text style={styles.confidenceNote}>Illustrative screening result</Text></View><Text style={styles.confidenceValue}>92<Text style={styles.confidencePercent}>%</Text></Text></View>
            <View style={styles.confidenceTrack}><View style={styles.confidenceFill} /></View>
            <View style={styles.evidenceMetrics}>
              <View style={styles.evidenceMetric}><Text style={styles.evidenceMetricLabel}>LiDAR DEPTH</Text><Text style={styles.evidenceMetricValue}>43 <Text style={styles.evidenceMetricUnit}>mm</Text></Text></View>
              <View style={styles.evidenceMetric}><Text style={styles.evidenceMetricLabel}>IMU IMPACT</Text><Text style={styles.evidenceMetricValue}>3.1 <Text style={styles.evidenceMetricUnit}>σ</Text></Text></View>
              <View style={[styles.evidenceMetric, styles.evidenceMetricLast]}><Text style={styles.evidenceMetricLabel}>THERMAL ANOMALY</Text><Text style={styles.evidenceMetricValue}>YES</Text></View>
            </View>
            <Text style={styles.evidenceDisclaimer}>Example readings only. A device payload format and live sensor connection have not been supplied.</Text>
          </View>

          <View style={styles.recommendationSection}>
            <SectionHeading index="02" title="Inspection recommendation" meta="DEMO" />
            <View style={styles.recommendationCard}>
              <View style={styles.recommendationHeader}>
                <View style={styles.recommendationSymbol}><Feather name="clipboard" size={20} color={C.primary} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recommendationKicker}>HIGH SCREENING PRIORITY</Text>
                  <Text style={styles.recommendationTitle}>Targeted pavement inspection</Text>
                </View>
              </View>
              <Text style={styles.recommendationReason}>Why this surfaced: the sample vision result identifies a pothole at 92% confidence, alongside a 43 mm LiDAR depth reading and a 3.1σ IMU impact. Together, these merit a closer look—not a structural-safety diagnosis.</Text>
              <View style={styles.reviewBanner}><Feather name="user-check" size={17} color={C.primary} /><Text style={styles.reviewBannerText}>Human review required before any field action. No automatic dispatch.</Text></View>
            </View>
          </View>

          <View style={styles.contextIntro}>
            <SectionHeading index="03" title="Environmental context" meta="LIVE API" />
            <Text style={styles.contextDescription}>Government source data for the selected demonstration location. Context is not defect evidence.</Text>
          </View>
          <View style={styles.contextToolbar}>
            <View style={styles.contextLive}><View style={styles.liveDot} /><Text style={styles.contextLiveText}>GOVERNMENT SOURCES</Text></View>
            <Pressable testID="refresh-context" accessibilityRole="button" accessibilityLabel="Refresh environmental context" onPress={refresh} disabled={isFetching} style={({ pressed }) => [styles.refreshButton, pressed && styles.pressed, isFetching && styles.disabled]}>
              <Feather name="refresh-cw" size={16} color={C.primary} /><Text style={styles.refreshText}>{isFetching ? 'Updating' : 'Refresh'}</Text>
            </Pressable>
          </View>

          {isPending ? (
            <><Skeleton /><Skeleton /></>
          ) : isError && !data ? (
            <View style={styles.errorCard}>
              <Feather name="wifi-off" size={24} color={C.destructive} />
              <Text style={styles.errorTitle}>Context could not be reached</Text>
              <Text style={styles.errorBody}>The government context service did not respond. Demo detection evidence above remains sample data.</Text>
              <Pressable testID="retry-context" accessibilityRole="button" onPress={refresh} style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}><Text style={styles.retryText}>Try again</Text><Feather name="arrow-right" size={16} color={C.primaryForeground} /></Pressable>
            </View>
          ) : (
            <>
              {isError && <Text style={styles.staleNotice}>Refresh failed. Showing the last available context.</Text>}
              <View style={styles.contextCard}>
                <View style={styles.cardHeading}><View style={styles.cardHeadingLeft}><Feather name="cloud" size={20} color={C.primary} /><View><Text style={styles.cardTitle}>Weather & alerts</Text><Text style={styles.cardProvider}>{weather?.provider ?? 'National Weather Service'}</Text></View></View><SourceStatus status={weather?.status ?? 'unavailable'} /></View>
                {weather?.status === 'unavailable' ? (
                  <View style={styles.unavailableBox}><Feather name="cloud-off" size={20} color={C.mutedForeground} /><Text style={styles.unavailableText}>{weather.error || 'Weather provider is currently unavailable for this location.'}</Text></View>
                ) : (
                  <>
                    {weather?.temperature != null || weather?.shortForecast ? (
                      <View style={styles.weatherMain}><Text style={styles.temperature}>{weather.temperature != null ? `${Math.round(weather.temperature)}°` : '—'}</Text><View style={{ flex: 1 }}><Text style={styles.temperatureUnit}>FORECAST {weather.temperatureUnit || 'TEMPERATURE'}</Text><Text style={styles.forecast}>{weather.shortForecast || 'Forecast not reported'}</Text></View></View>
                    ) : <Text style={styles.inlineEmpty}>Hourly forecast was not reported by this provider.</Text>}
                    <View style={styles.weatherMetrics}>
                      <Metric icon="droplet" label="PRECIPITATION" value={weather?.precipitationProbability != null ? `${weather.precipitationProbability}` : '—'} unit={weather?.precipitationProbability != null ? '%' : undefined} detail="Probability" />
                      <Metric icon="wind" label="WIND" value={weather?.windSpeed || '—'} detail="Forecast speed" />
                    </View>
                    {weather?.error ? <Text style={styles.partialNotice}>{weather.error}</Text> : null}
                    <View style={styles.subSectionHeader}><Text style={styles.subSectionTitle}>Active alerts</Text><Text style={styles.subSectionCount}>{weather?.error?.includes('Alerts:') ? 'UNCONFIRMED' : `${weather?.alerts.length ?? 0} FOUND`}</Text></View>
                    {weather?.alerts.length ? weather.alerts.map(alert => <AlertRow key={alert.id} alert={alert} />) : <View style={styles.emptyRow}><Feather name={weather?.error?.includes('Alerts:') ? 'alert-circle' : 'check-circle'} size={18} color={weather?.error?.includes('Alerts:') ? C.signal : C.success} /><Text style={styles.emptyRowText}>{weather?.error?.includes('Alerts:') ? 'Alert feed could not be checked; absence of alerts is not confirmed.' : 'No active alerts reported for this location.'}</Text></View>}
                  </>
                )}
              </View>

              <View style={styles.contextCard}>
                <View style={styles.cardHeading}><View style={styles.cardHeadingLeft}><Feather name="activity" size={20} color={C.primary} /><View><Text style={styles.cardTitle}>Nearby seismic activity</Text><Text style={styles.cardProvider}>{earthquakes?.provider ?? 'US Geological Survey'} · {earthquakes?.radiusMiles ?? RADIUS_MILES} mi radius</Text></View></View><SourceStatus status={earthquakes?.status ?? 'unavailable'} /></View>
                {earthquakes?.status === 'unavailable' ? (
                  <View style={styles.unavailableBox}><Feather name="wifi-off" size={20} color={C.mutedForeground} /><Text style={styles.unavailableText}>{earthquakes.error || 'Earthquake provider is currently unavailable.'}</Text></View>
                ) : (
                  <>
                    {earthquakes?.error ? <Text style={styles.partialNotice}>{earthquakes.error}</Text> : null}
                    {earthquakes?.events.length ? earthquakes.events.map(event => <QuakeRow key={event.id} event={event} />) : <View style={styles.seismicEmpty}><View style={styles.seismicEmptyIcon}><Feather name={earthquakes?.status === 'partial' ? 'alert-circle' : 'minus'} size={22} color={earthquakes?.status === 'partial' ? C.signal : C.success} /></View><Text style={styles.seismicEmptyTitle}>{earthquakes?.status === 'partial' ? 'Event coverage incomplete' : 'No nearby events reported'}</Text><Text style={styles.seismicEmptyBody}>{earthquakes?.status === 'partial' ? 'The event feed did not fully report results for this location.' : 'No earthquake events returned within the selected radius.'}</Text></View>}
                  </>
                )}
              </View>
              <Text style={styles.generatedAt}>CONTEXT GENERATED  {formatTime(data?.generatedAt)}{'\n'}SOURCE LOCATION  {data?.location.latitude.toFixed(4)}, {data?.location.longitude.toFixed(4)}</Text>
            </>
          )}
          <View style={styles.dataSection}>
            <SectionHeading index="04" title="Data needed from device" />
            <Text style={styles.dataIntro}>Use existing fleet vehicles to collect camera, IMU and GPS evidence. LiDAR and thermal readings enrich a pass when available.</Text>
            <View style={styles.dataCard}>
              <View style={styles.dataGroupHeading}><View style={styles.coreDot} /><Text style={styles.dataGroupLabel}>CORE PAYLOAD</Text></View>
              <View style={styles.dataRow}><Text style={styles.dataRowName}>Identity</Text><Text style={styles.dataRowValue}>Event ID · Device ID · ISO timestamp</Text></View>
              <View style={styles.dataRow}><Text style={styles.dataRowName}>Position</Text><Text style={styles.dataRowValue}>GPS coordinates · Accuracy</Text></View>
              <View style={styles.dataRow}><Text style={styles.dataRowName}>Vision</Text><Text style={styles.dataRowValue}>Class · Confidence · Image reference</Text></View>
              <View style={styles.dataRow}><Text style={styles.dataRowName}>Motion</Text><Text style={styles.dataRowValue}>Calibrated IMU impact · Vehicle speed</Text></View>
              <View style={styles.optionalGroup}>
                <View style={styles.dataGroupHeading}><View style={styles.optionalDot} /><Text style={styles.dataGroupLabel}>OPTIONAL ENRICHMENT</Text></View>
                <Text style={styles.optionalText}>LiDAR depth · Thermal delta · Segment ID · Repeat-pass history</Text>
              </View>
            </View>
            <View style={styles.trendNote}><Feather name="layers" size={16} color={C.mutedForeground} /><Text style={styles.trendNoteText}>Trends and repair verification require repeated, dated observations of the same road segment. This single demo detection cannot show either.</Text></View>
          </View>
          <View style={styles.footerNote}><Feather name="map" size={16} color={C.mutedForeground} /><Text style={styles.footerNoteText}>Map integration awaits a Google Maps SDK key. No map or device position is shown here.</Text></View>
          <View style={styles.footerRule} /><Text style={styles.footerBrand}>ROADWATCH  /  ANALYST VIEW</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: { width: '100%', maxWidth: 720, alignSelf: 'center', paddingHorizontal: 18 },
  masthead: { backgroundColor: C.ink, borderRadius: 18, paddingHorizontal: 22, paddingTop: 21, overflow: 'hidden' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  brandMark: { width: 24, height: 24, borderWidth: 1, borderColor: C.signal, borderRadius: 5, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 4, transform: [{ rotate: '-18deg' }] },
  brandMarkLine: { width: 2, height: 15, backgroundColor: C.signal },
  brandMarkLineShort: { width: 2, height: 9, backgroundColor: C.signal },
  brand: { color: C.primaryForeground, fontSize: 16, fontWeight: '800', letterSpacing: 2.2 },
  edition: { color: '#8EA4A4', marginLeft: 'auto', fontFamily: MONO, fontSize: 9, letterSpacing: 1 },
  headerRule: { height: 1, backgroundColor: C.grid, marginTop: 21 },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 25 },
  eyebrow: { color: '#A5B8B3', fontSize: 10, fontWeight: '700', letterSpacing: 1.55 },
  heroIndex: { color: C.signal, fontFamily: MONO, fontSize: 10 },
  heroTitle: { color: '#F1F5EC', fontSize: 37, fontWeight: '700', letterSpacing: -1.7, lineHeight: 42, marginTop: 12 },
  heroSubtitle: { color: '#ADBFBC', fontSize: 13, lineHeight: 20, marginTop: 12, maxWidth: 290, marginBottom: 29 },
  heroFooter: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderTopColor: C.grid, height: 48, gap: 7 },
  heroFooterDot: { height: 6, width: 6, borderRadius: 3, backgroundColor: C.signal },
  heroFooterText: { color: '#AEC1BC', fontFamily: MONO, fontSize: 9, letterSpacing: .7 },
  heroFooterRight: { marginLeft: 'auto', color: '#779491', fontFamily: MONO, fontSize: 9, letterSpacing: .4 },
  locationBlock: { paddingTop: 26, paddingBottom: 25 },
  locationTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { fontFamily: MONO, color: C.mutedForeground, fontSize: 10, letterSpacing: 1, fontWeight: '600' },
  labelLight: { color: '#94AAA8' },
  locationName: { color: C.foreground, fontSize: 26, fontWeight: '700', letterSpacing: -.8, marginTop: 5 },
  locationState: { color: C.mutedForeground, fontWeight: '400' },
  coordinate: { color: C.mutedForeground, fontFamily: MONO, fontSize: 10, marginTop: 7, letterSpacing: .1 },
  locationChoices: { gap: 8, paddingTop: 17, paddingRight: 18 },
  locationChip: { minHeight: 43, paddingHorizontal: 15, borderRadius: 23, borderWidth: 1, borderColor: C.border, alignItems: 'center', justifyContent: 'center', backgroundColor: C.card },
  locationChipSelected: { backgroundColor: C.primary, borderColor: C.primary },
  locationChipText: { color: C.inkSoft, fontSize: 12, fontWeight: '600' },
  locationChipTextSelected: { color: C.primaryForeground },
  pressed: { opacity: .65 },
  sectionHeading: { flexDirection: 'row', alignItems: 'center', gap: 9, marginBottom: 13 },
  sectionNumber: { backgroundColor: C.ink, borderRadius: 4, minWidth: 26, height: 25, alignItems: 'center', justifyContent: 'center' },
  sectionNumberText: { color: C.primaryForeground, fontFamily: MONO, fontSize: 10 },
  sectionTitle: { color: C.foreground, fontSize: 17, fontWeight: '700', letterSpacing: -.4, flex: 1 },
  sectionMeta: { color: C.mutedForeground, fontFamily: MONO, fontSize: 10, letterSpacing: .8 },
  evidenceCard: { backgroundColor: C.ink, borderRadius: 15, overflow: 'hidden', paddingTop: 19, paddingHorizontal: 18 },
  evidenceTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  demoTag: { flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1, paddingTop: 5 },
  demoDot: { backgroundColor: C.signal, height: 6, width: 6, borderRadius: 3 },
  demoTagText: { color: '#B4C3BB', fontFamily: MONO, fontSize: 9, letterSpacing: .2, flexShrink: 1 },
  priority: { backgroundColor: C.signal, borderRadius: 4, paddingHorizontal: 8, paddingVertical: 6 },
  priorityText: { color: C.ink, fontFamily: MONO, fontWeight: '800', fontSize: 9, letterSpacing: .3 },
  defectHeading: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 27 },
  defectGlyph: { width: 43, height: 43, borderRadius: 9, borderWidth: 1, borderColor: C.grid, alignItems: 'center', justifyContent: 'center' },
  defectKicker: { color: '#93AAA8', fontFamily: MONO, fontSize: 9, letterSpacing: .5 },
  defectTitle: { color: C.primaryForeground, fontSize: 28, fontWeight: '700', letterSpacing: -.9, marginTop: 2 },
  confidenceRow: { marginTop: 27, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  confidenceNote: { color: '#7F9C9C', fontSize: 11, marginTop: 5 },
  confidenceValue: { color: '#F4F7EF', fontSize: 43, lineHeight: 45, fontWeight: '700', letterSpacing: -2 },
  confidencePercent: { color: C.signal, fontSize: 23 },
  confidenceTrack: { height: 5, backgroundColor: C.grid, borderRadius: 3, marginTop: 12, overflow: 'hidden' },
  confidenceFill: { width: '92%', height: 5, backgroundColor: C.signal, borderRadius: 3 },
  evidenceMetrics: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.grid, marginTop: 25, paddingTop: 17 },
  evidenceMetric: { flex: 1, paddingLeft: 11, borderRightWidth: 1, borderRightColor: C.grid },
  evidenceMetricLast: { borderRightWidth: 0 },
  evidenceMetricLabel: { color: '#8EA8A5', fontFamily: MONO, fontSize: 8, letterSpacing: .1 },
  evidenceMetricValue: { color: '#F4F7EF', fontSize: 22, fontWeight: '700', letterSpacing: -.6, marginTop: 7 },
  evidenceMetricUnit: { fontSize: 13, color: '#AEC4BB', fontWeight: '400' },
  evidenceDisclaimer: { color: '#829D9B', fontSize: 10, lineHeight: 15, borderTopWidth: 1, borderTopColor: C.grid, marginTop: 18, paddingVertical: 13 },
  recommendationSection: { marginTop: 28 },
  recommendationCard: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 14, padding: 18, borderLeftWidth: 4, borderLeftColor: C.signal },
  recommendationHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  recommendationSymbol: { height: 39, width: 39, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: C.accent },
  recommendationKicker: { fontFamily: MONO, color: '#98623F', fontSize: 9, fontWeight: '700', letterSpacing: .6 },
  recommendationTitle: { color: C.foreground, fontSize: 17, fontWeight: '700', letterSpacing: -.4, marginTop: 4 },
  recommendationReason: { color: C.inkSoft, fontSize: 12, lineHeight: 19, marginTop: 17 },
  reviewBanner: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 8, backgroundColor: C.accent, marginTop: 17 },
  reviewBannerText: { color: C.accentForeground, fontSize: 11, fontWeight: '600', lineHeight: 16, flex: 1 },
  dataSection: { marginTop: 30 },
  dataIntro: { color: C.mutedForeground, fontSize: 12, lineHeight: 18, marginTop: -4, marginBottom: 14 },
  dataCard: { backgroundColor: C.card, borderWidth: 1, borderColor: C.border, borderRadius: 14, paddingHorizontal: 17, paddingTop: 17, paddingBottom: 16 },
  dataGroupHeading: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 10 },
  coreDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.primary },
  optionalDot: { width: 6, height: 6, borderRadius: 3, borderWidth: 1, borderColor: C.mutedForeground },
  dataGroupLabel: { fontFamily: MONO, fontWeight: '700', fontSize: 9, color: C.mutedForeground, letterSpacing: .7 },
  dataRow: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 11, gap: 9 },
  dataRowName: { color: C.foreground, fontWeight: '700', fontSize: 11, width: 58 },
  dataRowValue: { color: C.inkSoft, fontSize: 11, lineHeight: 16, flex: 1 },
  optionalGroup: { paddingTop: 15, borderTopWidth: 1, borderTopColor: C.border },
  optionalText: { color: C.inkSoft, fontSize: 11, lineHeight: 17 },
  trendNote: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingHorizontal: 3, marginTop: 13 },
  trendNoteText: { color: C.mutedForeground, fontSize: 11, lineHeight: 17, flex: 1 },
  contextIntro: { marginTop: 34 },
  contextDescription: { color: C.mutedForeground, fontSize: 12, lineHeight: 18, marginBottom: 16, marginTop: -5 },
  contextToolbar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  contextLive: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  liveDot: { height: 7, width: 7, borderRadius: 4, backgroundColor: C.success },
  contextLiveText: { fontFamily: MONO, fontSize: 9, color: C.success, letterSpacing: .5 },
  refreshButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7, minHeight: 44, minWidth: 88 },
  refreshText: { color: C.primary, fontWeight: '700', fontSize: 12 },
  disabled: { opacity: .5 },
  skeletonCard: { backgroundColor: C.card, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 20, marginBottom: 12, height: 173 },
  skeleton: { backgroundColor: C.muted, borderRadius: 5 },
  errorCard: { backgroundColor: C.card, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 22, marginBottom: 12 },
  errorTitle: { color: C.foreground, fontSize: 19, fontWeight: '700', marginTop: 14 },
  errorBody: { color: C.mutedForeground, fontSize: 13, lineHeight: 19, marginTop: 7 },
  retryButton: { backgroundColor: C.primary, minHeight: 44, alignSelf: 'flex-start', paddingHorizontal: 17, borderRadius: 8, flexDirection: 'row', gap: 12, alignItems: 'center', marginTop: 20 },
  retryText: { color: C.primaryForeground, fontWeight: '700', fontSize: 13 },
  staleNotice: { color: C.destructive, fontSize: 12, marginBottom: 12 },
  contextCard: { backgroundColor: C.card, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 18, marginBottom: 12 },
  cardHeading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
  cardHeadingLeft: { flexDirection: 'row', gap: 10, alignItems: 'center', flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: C.foreground, letterSpacing: -.3 },
  cardProvider: { fontSize: 10, color: C.mutedForeground, marginTop: 3 },
  sourceStatus: { borderRadius: 4, paddingVertical: 5, paddingHorizontal: 6, flexDirection: 'row', alignItems: 'center', gap: 4 },
  statusAvailable: { backgroundColor: '#E4EFE8' },
  statusPartial: { backgroundColor: C.signalPale },
  statusUnavailable: { backgroundColor: '#F8EAE6' },
  statusDot: { height: 5, width: 5, borderRadius: 3 },
  sourceStatusText: { fontFamily: MONO, fontSize: 8, fontWeight: '700' },
  weatherMain: { flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 24, paddingBottom: 20 },
  temperature: { fontSize: 53, lineHeight: 56, fontWeight: '600', color: C.foreground, letterSpacing: -2.5 },
  temperatureUnit: { fontFamily: MONO, fontSize: 9, color: C.mutedForeground, letterSpacing: .6 },
  forecast: { color: C.foreground, fontSize: 14, fontWeight: '600', marginTop: 5, lineHeight: 18 },
  weatherMetrics: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.border, paddingTop: 17, gap: 15 },
  metric: { flex: 1 },
  metricTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metricLabel: { fontFamily: MONO, fontSize: 9, color: C.mutedForeground, letterSpacing: .2 },
  metricValueRow: { flexDirection: 'row', alignItems: 'baseline', gap: 3, marginTop: 8 },
  metricValue: { fontSize: 20, fontWeight: '700', color: C.foreground },
  metricUnit: { fontSize: 12, color: C.mutedForeground },
  metricDetail: { color: C.mutedForeground, fontSize: 10, marginTop: 2 },
  subSectionHeader: { borderTopWidth: 1, borderTopColor: C.border, marginTop: 19, paddingTop: 16, flexDirection: 'row', justifyContent: 'space-between' },
  subSectionTitle: { fontSize: 14, fontWeight: '700', color: C.foreground },
  subSectionCount: { fontFamily: MONO, fontSize: 9, color: C.mutedForeground },
  emptyRow: { flexDirection: 'row', alignItems: 'center', gap: 9, backgroundColor: C.muted, borderRadius: 8, marginTop: 13, padding: 13 },
  emptyRowText: { color: C.inkSoft, fontSize: 11, flex: 1 },
  unavailableBox: { backgroundColor: C.muted, borderRadius: 9, padding: 16, marginTop: 18, flexDirection: 'row', gap: 11, alignItems: 'center' },
  unavailableText: { color: C.mutedForeground, fontSize: 12, lineHeight: 17, flex: 1 },
  inlineEmpty: { color: C.mutedForeground, fontSize: 12, marginVertical: 19 },
  partialNotice: { color: '#98623F', fontSize: 11, lineHeight: 16, marginTop: 14 },
  alertRow: { flexDirection: 'row', gap: 10, paddingTop: 15 },
  alertIcon: { width: 29, height: 29, borderRadius: 6, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F8EAE6' },
  alertEvent: { color: C.destructive, fontSize: 13, fontWeight: '700' },
  alertHeadline: { color: C.foreground, fontSize: 12, lineHeight: 17, marginTop: 4 },
  alertMeta: { color: C.mutedForeground, fontSize: 10, marginTop: 5 },
  sourceLink: { minHeight: 44, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 7 },
  sourceLinkText: { color: C.primary, fontSize: 11, fontWeight: '700' },
  quakeRow: { borderTopWidth: 1, borderTopColor: C.border, marginTop: 15, paddingTop: 15, flexDirection: 'row', gap: 13 },
  magnitude: { height: 48, width: 48, borderRadius: 9, backgroundColor: C.secondary, alignItems: 'center', justifyContent: 'center' },
  magnitudeText: { color: C.primary, fontSize: 17, fontWeight: '800' },
  magnitudeLabel: { color: C.mutedForeground, fontFamily: MONO, fontSize: 8 },
  quakePlace: { color: C.foreground, fontSize: 13, fontWeight: '700', lineHeight: 18 },
  quakeDetail: { color: C.mutedForeground, fontSize: 11, marginTop: 4 },
  seismicEmpty: { alignItems: 'center', paddingVertical: 27, borderTopWidth: 1, borderTopColor: C.border, marginTop: 17 },
  seismicEmptyIcon: { height: 38, width: 38, borderRadius: 19, backgroundColor: '#E4EFE8', alignItems: 'center', justifyContent: 'center' },
  seismicEmptyTitle: { fontSize: 13, fontWeight: '700', color: C.foreground, marginTop: 10 },
  seismicEmptyBody: { fontSize: 11, color: C.mutedForeground, marginTop: 4, textAlign: 'center' },
  generatedAt: { fontFamily: MONO, fontSize: 9, lineHeight: 17, color: C.mutedForeground, marginTop: 5, letterSpacing: .2 },
  footerNote: { backgroundColor: C.muted, borderRadius: 9, padding: 15, flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginTop: 25 },
  footerNoteText: { color: C.mutedForeground, fontSize: 11, lineHeight: 17, flex: 1 },
  footerRule: { height: 1, backgroundColor: C.border, marginTop: 27 },
  footerBrand: { fontFamily: MONO, fontSize: 9, color: C.mutedForeground, letterSpacing: 1, marginTop: 14 },
});