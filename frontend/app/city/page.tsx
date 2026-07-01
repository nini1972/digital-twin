'use client';

import dynamic from 'next/dynamic';
import { useState, useEffect, useRef, useCallback } from 'react';
import { Bot, User, Send, Loader2, Activity, Zap, Car, Radio } from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Resident = {
  id: string; x: number; y: number;
  battery: number; battery_raw: number; battery_capacity: number; vehicle_type: string; charging: boolean; state: string;
  soh: number; aero_drag: number; regen_efficiency: number;
  battery_temperature: number; payload_weight: number;
};

type Hub = {
  id: string; x: number; y: number;
  active: boolean; price: number; queue: number;
  capacity: number; charging_slots: string[]; slots_used?: number;
  waiting?: number; charging?: number; queue_total?: number;
};

type TrafficAgent = { id: string; x: number; y: number };

type SimulationMetrics = {
  total_city_grid_load_kw: number;
  ev_power_demand_kw: number;
  co2_saved_kg_h: number;
  avg_fleet_soh: number;
};

type ForecastData = {
  horizon_ticks: number;
  weather: string;
  projected_total_queue: number;
  projected_avg_price: number;
  projected_hotspots: { zone: string; congestion: number }[];
  confidence: number;
  recommendations: string[];
};

type SegmentDetails = {
  count: number;
  ratio: number;
};

type SegmentData = {
  residents: number;
  battery_segments: {
    battery_critical: SegmentDetails;
    battery_low: SegmentDetails;
    battery_mid: SegmentDetails;
    battery_high: SegmentDetails;
  };
  state_segments: Record<string, SegmentDetails>;
  charging_pressure_index: number;
  demand_risk_band: 'low' | 'medium' | 'high';
};

type LiveTrafficEvent = {
  id: string;
  event_type: 'accident' | 'queue';
  description: string;
  x: number;
  y: number;
  zone_key: string;
};

type CityState = {
  residents: Resident[];
  hubs: Hub[];
  traffic: TrafficAgent[];
  zone_congestion: Record<string, number>;
  zone_speed_limits: Record<string, number>;
  traffic_incident_speed_limits?: Record<string, number>;
  weather?: string;
  metrics?: SimulationMetrics;
  live_traffic_events?: LiveTrafficEvent[];
};

type ChatMessage = { role: 'user' | 'assistant'; content: string };
type TelemetryRow = { timestamp: string; weather?: string; active_hubs: number; avg_price: number; total_queue: number; avg_temp?: number; avg_drag?: number };

type Decision = {
  agent: string; type: string; description: string;
  confidence: number; tick: number | null; at: string;
};

type StartMode = 'smooth' | 'immediate';

const START_MODE_STORAGE_KEY = 'city_start_mode';

function SidebarPanelSkeleton({ title, className }: { title: string; className: string }) {
  return (
    <div className={`p-6 rounded-2xl border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl ${className}`}>
      <div className="animate-pulse space-y-4">
        <div className="h-3 w-28 rounded-full bg-white/10" />
        <div className="h-5 w-52 rounded-full bg-white/10" />
        <div className="space-y-2">
          <div className="h-10 rounded-2xl bg-white/5" />
          <div className="h-10 rounded-2xl bg-white/5" />
          <div className="h-10 rounded-2xl bg-white/5" />
        </div>
        <p className="text-xs text-slate-500">Loading {title}…</p>
      </div>
    </div>
  );
}

const CityScenarioLab = dynamic(() => import('@/components/city-scenario-lab'), {
  ssr: false,
  loading: () => <SidebarPanelSkeleton title="Scenario Lab" className="min-h-[520px]" />,
});

const PolicyDashboard = dynamic(() => import('@/components/policy-dashboard'), {
  ssr: false,
  loading: () => <SidebarPanelSkeleton title="Policy Dashboard" className="min-h-[760px]" />,
});

const ProfitMarginWidget = dynamic(() => import('@/components/ProfitMarginWidget').then(mod => mod.ProfitMarginWidget), {
  ssr: false,
  loading: () => <SidebarPanelSkeleton title="Financial Margins" className="min-h-[290px]" />,
});

// ---------------------------------------------------------------------------
// Sparkline
// ---------------------------------------------------------------------------

function Sparkline({ values, color = '#60a5fa' }: { values: number[]; color?: string }) {
  if (values.length < 2) return <div className="h-10 bg-white/5 rounded" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 260; const H = 40;
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * W},${H - ((v - min) / range) * H}`)
    .join(' ');
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}



// ---------------------------------------------------------------------------
// API base URL
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WS_BASE = API_BASE.replace(/^http/, 'ws');

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CityTwinPage() {
  const [startMode, setStartMode] = useState<StartMode>('smooth');
  const [liveFeedEnabled, setLiveFeedEnabled] = useState(false);
  const [cityState, setCityState] = useState<CityState>({
    residents: [], hubs: [], traffic: [], zone_congestion: {}, zone_speed_limits: {}, traffic_incident_speed_limits: {}, weather: undefined, live_traffic_events: [],
  });
  const [showTrails, setShowTrails] = useState(true);
  const [showResidentIds, setShowResidentIds] = useState(true);
  const [residentFilter, setResidentFilter] = useState('');
  const [trails, setTrails] = useState<Record<string, { x: number; y: number }[]>>({});
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryRow[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [segments, setSegments] = useState<SegmentData | null>(null);
  const [recommendations, setRecommendations] = useState<string[]>([]);
  const [oracleMode, setOracleMode] = useState<'advisor' | 'autopilot'>('advisor');
  const isTogglingRef = useRef(false);
  const [hoveredResidentId, setHoveredResidentId] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevHubPricesRef = useRef<Record<string, number>>({});

  // Load persisted start mode preference once on mount.
  useEffect(() => {
    try {
      const persistedMode = window.localStorage.getItem(START_MODE_STORAGE_KEY);
      if (persistedMode === 'smooth' || persistedMode === 'immediate') {
        setStartMode(persistedMode);
      }
    } catch {
      // Ignore localStorage failures.
    }
  }, []);

  // Persist start mode preference changes.
  useEffect(() => {
    try {
      window.localStorage.setItem(START_MODE_STORAGE_KEY, startMode);
    } catch {
      // Ignore localStorage failures.
    }
  }, [startMode]);

  // Configure live feed start behavior based on selected mode.
  useEffect(() => {
    if (liveFeedEnabled) {
      return;
    }

    if (startMode === 'immediate') {
      setLiveFeedEnabled(true);
      return;
    }

    const timer = setTimeout(() => setLiveFeedEnabled(true), 4500);
    return () => clearTimeout(timer);
  }, [startMode, liveFeedEnabled]);

  // --- Derived sparklines ---
  const priceHistory = telemetry.map(t => t.avg_price);
  const queueHistory = telemetry.map(t => t.total_queue);
  const tempHistory = telemetry.map(t => t.avg_temp ?? 0);
  const dragHistory = telemetry.map(t => t.avg_drag ?? 0);

  // --- WebSocket ---
  useEffect(() => {
    if (!liveFeedEnabled) {
      return;
    }

    let isUnmounting = false;

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/city`);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        try {
          const data: CityState = JSON.parse(evt.data);
          setCityState(data);
          if (showTrails) {
            setTrails(prev => {
              const next = { ...prev };
              data.residents.forEach(r => {
                const hist = next[r.id] ?? [];
                next[r.id] = [...hist.slice(-20), { x: r.x, y: r.y }];
              });
              return next;
            });
          }
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        if (!isUnmounting) {
          reconnectTimerRef.current = setTimeout(connect, 1500);
        }
      };
    };

    connect();

    return () => {
      isUnmounting = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveFeedEnabled]);

  // --- City-only telemetry from live WS state ---
  useEffect(() => {
    if (!liveFeedEnabled) return;
    if (!cityState.hubs.length) return;
    const activeHubs = cityState.hubs.filter(h => h.active);
    const avgPrice = activeHubs.length
      ? activeHubs.reduce((sum, h) => sum + h.price, 0) / activeHubs.length
      : 0;
    const totalQueue = cityState.hubs.reduce(
      (sum, h) => sum + (h.waiting ?? h.queue ?? 0),
      0
    );
    const row: TelemetryRow = {
      timestamp: new Date().toISOString(),
      weather: cityState.weather,
      active_hubs: activeHubs.length,
      avg_price: Number(avgPrice.toFixed(4)),
      total_queue: totalQueue,
      avg_temp: cityState.residents.length ? cityState.residents.reduce((sum, r) => sum + (r.battery_temperature || 0), 0) / cityState.residents.length : 0,
      avg_drag: cityState.residents.length ? cityState.residents.reduce((sum, r) => sum + (r.aero_drag || 0), 0) / cityState.residents.length : 0,
    };
    setTelemetry(prev => [...prev.slice(-119), row]);
  }, [cityState.hubs, cityState.weather, cityState.residents, liveFeedEnabled]);

  // --- Chief decisions polling ---
  useEffect(() => {
    if (!liveFeedEnabled) {
      return;
    }

    let idleId: number | null = null;
    let timerId: ReturnType<typeof setTimeout> | null = null;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchDecisions = async () => {
      try {
        const res = await fetch(`${API_BASE}/city/decisions?limit=8`, { credentials: 'include' });
        if (res.ok) {
          const d = await res.json();
          const rows: Decision[] = d.decisions ?? [];
          const deduped = rows.filter((row, idx, arr) => {
            const firstIndex = arr.findIndex(
              (x) => x.type === row.type && x.description === row.description
            );
            return firstIndex === idx;
          });
          setDecisions(deduped);
        }
      } catch { /* ignore */ }
    };
    const fetchAnalytics = async () => {
      try {
        const [fRes, sRes, rRes] = await Promise.all([
          fetch(`${API_BASE}/city/forecast?horizon=30`, { credentials: 'include' }),
          fetch(`${API_BASE}/city/segments`, { credentials: 'include' }),
          fetch(`${API_BASE}/city/recommendations`, { credentials: 'include' })
        ]);
        if (fRes.ok) setForecast(await fRes.json());
        if (sRes.ok) setSegments(await sRes.json());
        if (rRes.ok) setRecommendations((await rRes.json()).recommendations || []);
      } catch { /* ignore */ }
    };
    const fetchOracleMode = async () => {
      if (isTogglingRef.current) return;
      try {
        const res = await fetch(`${API_BASE}/city/oracle/mode`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          setOracleMode(data.mode);
        }
      } catch { /* ignore */ }
    };

    const startPolling = () => {
      void fetchDecisions();
      void fetchAnalytics();
      void fetchOracleMode();
      intervalId = setInterval(() => {
        void fetchDecisions();
        void fetchAnalytics();
        void fetchOracleMode();
      }, 8_000);
    };

    if ('requestIdleCallback' in window) {
      idleId = window.requestIdleCallback(startPolling, { timeout: 1800 });
    } else {
      timerId = setTimeout(startPolling, 350);
    }

    return () => {
      if (idleId !== null && 'cancelIdleCallback' in window) {
        window.cancelIdleCallback(idleId);
      }
      if (timerId) {
        clearTimeout(timerId);
      }
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [liveFeedEnabled]);

  // --- Chat auto-scroll ---
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // --- Action helpers ---
  const sendWs = useCallback((cmd: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(cmd);
  }, []);

  const addResident = () => sendWs('add_resident');
  const addHub = () => sendWs('add_hub');
  const addTraffic = () => sendWs('add_traffic');

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isChatting) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsChatting(true);
    try {
      const res = await fetch(`${API_BASE}/city/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, session_id: sessionId }),
        credentials: 'include',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!sessionId) setSessionId(data.session_id);
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (err) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err}` }]);
    } finally {
      setIsChatting(false);
    }
  };

  const toggleOracleMode = async () => {
    if (isTogglingRef.current) return;
    isTogglingRef.current = true;
    const newMode = oracleMode === 'advisor' ? 'autopilot' : 'advisor';
    setOracleMode(newMode);
    try {
      const res = await fetch(`${API_BASE}/city/oracle/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setOracleMode(data.mode);
      } else {
        setOracleMode(oracleMode);
      }
    } catch {
      setOracleMode(oracleMode);
    } finally {
      setTimeout(() => {
        isTogglingRef.current = false;
      }, 1500);
    }
  };

  // ---------------------------------------------------------------------------
  // Derived simulation stats
  // ---------------------------------------------------------------------------

  const chargingCount = cityState.residents.filter(r => r.charging).length;
  const seekingCount = cityState.residents.filter(r => r.state === 'seeking').length;
  const criticalCount = cityState.residents.filter(r => r.battery < 30).length;
  const congestionValues = Object.values(cityState.zone_congestion);
  const avgCongestion = congestionValues.length
    ? congestionValues.reduce((a, b) => a + b, 0) / congestionValues.length
    : 0;
  const maxCongestion = congestionValues.length ? Math.max(...congestionValues) : 0;
  const normalizedResidentFilter = residentFilter.trim().toLowerCase();
  const matchingResidents = cityState.residents.filter((r) => {
    const shortId = r.id.replace('res_', '').toLowerCase();
    return (
      shortId.includes(normalizedResidentFilter) ||
      r.id.toLowerCase().includes(normalizedResidentFilter)
    );
  });
  const selectedResidentId = normalizedResidentFilter
    ? (matchingResidents[0]?.id ?? null)
    : null;
  const selectedResident = selectedResidentId
    ? cityState.residents.find((r) => r.id === selectedResidentId) ?? null
    : null;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="city-page-shell min-h-screen text-white flex flex-col font-sans overflow-hidden">

      {/* Header */}
      <header className="flex items-center justify-between px-8 py-5 border-b border-white/5 shrink-0 z-10 relative">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-orange-400 via-amber-300 to-yellow-300 bg-clip-text text-transparent">
              City Digital Twin
            </h1>
            <span className="text-slate-500 font-light">— EV + Urban Traffic</span>
          </div>
          <span className="mt-1 inline-flex min-h-6 min-w-[118px] items-center gap-1 text-xs text-amber-400/70 bg-amber-400/5 border border-amber-400/10 rounded-full px-3 py-0.5">
            {cityState.weather ?? 'Weather: pending'}
          </span>
          <div className="mt-2 flex flex-col items-start">
            <div className="flex items-center rounded-full border border-white/10 bg-white/5 p-1">
              <button
                onClick={() => setStartMode('smooth')}
                title="Prioritize smooth load"
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${startMode === 'smooth' ? 'bg-orange-500/30 text-orange-200' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Smooth load
              </button>
              <button
                onClick={() => setStartMode('immediate')}
                title="Start simulation immediately"
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${startMode === 'immediate' ? 'bg-cyan-500/30 text-cyan-200' : 'text-slate-400 hover:text-slate-200'}`}
              >
                Immediate
              </button>
            </div>
            <span className="mt-1 pl-2 text-[10px] font-medium text-slate-500">
              Preference saved: {startMode === 'smooth' ? 'Smooth load' : 'Immediate'}
            </span>
          </div>
        </div>
        <div className="flex gap-3">
          <button onClick={() => setShowTrails(!showTrails)}
            className={`px-5 py-2 rounded-full border text-sm font-medium transition-all ${showTrails ? 'border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20' : 'border-slate-500/30 bg-slate-500/10 text-slate-400 hover:bg-slate-500/20'}`}>
            {showTrails ? 'Hide Trails' : 'Show Trails'}
          </button>
          <button onClick={() => setShowResidentIds(!showResidentIds)}
            className={`px-5 py-2 rounded-full border text-sm font-medium transition-all ${showResidentIds ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20' : 'border-slate-500/30 bg-slate-500/10 text-slate-400 hover:bg-slate-500/20'}`}>
            {showResidentIds ? 'Hide EV IDs' : 'Show EV IDs'}
          </button>
          <button onClick={addResident}
            className="px-5 py-2 rounded-full border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 text-sm font-medium transition-all">
            + EV Resident
          </button>
          <button onClick={addTraffic}
            className="px-5 py-2 rounded-full border border-yellow-500/30 bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-300 text-sm font-medium transition-all">
            + Traffic
          </button>
          <button onClick={addHub}
            className="px-5 py-2 rounded-full border border-pink-500/30 bg-pink-500/10 hover:bg-pink-500/20 text-pink-300 text-sm font-medium transition-all">
            + Hub
          </button>
        </div>
      </header>

      {/* Main */}
      <div className="flex-1 flex p-6 gap-6 relative z-10">

        {/* Canvas */}
        <div className="flex-1 relative rounded-[2rem] border border-white/5 bg-[#0a0a10]/80 backdrop-blur-3xl overflow-hidden shadow-2xl flex items-center justify-center group">
          {/* Glow blobs */}
          <div className="absolute top-0 left-0 w-[500px] h-[500px] bg-orange-600/8 blur-[120px] rounded-full mix-blend-screen pointer-events-none" />
          <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-blue-600/8 blur-[120px] rounded-full mix-blend-screen pointer-events-none" />
          {/* Grid */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:40px_40px] opacity-50" />

          {/* SVG Map */}
          <svg className="w-full h-full max-w-[800px] max-h-[800px] drop-shadow-2xl relative z-10" viewBox="-10 -10 120 120">

            {/* Zone Congestion Overlay */}
            {Array.from({ length: 5 }, (_, zx) =>
              Array.from({ length: 5 }, (_, zy) => {
                const key = `${zx},${zy}`;
                const level = cityState.zone_congestion[key] ?? 0;
                if (level < 0.1) return null;
                return (
                  <rect
                    key={key}
                    x={zx * 20} y={zy * 20}
                    width={20} height={20}
                    fill={`rgba(239,68,68,${(level * 0.35).toFixed(3)})`}
                    stroke="rgba(239,68,68,0.15)"
                    strokeWidth="0.3"
                    rx="0.5"
                    className="transition-all duration-500"
                  />
                );
              })
            )}

            {/* Live Belgian Traffic Incidents Overlay (pulsing orange border + warning symbol) */}
            {cityState.live_traffic_events?.map(ev => {
              const [zx, zy] = ev.zone_key.split(',').map(Number);
              const isAccident = ev.event_type === 'accident';
              return (
                <g key={`live-traffic-${ev.id}`}>
                  {/* Pulsing overlay rect */}
                  <rect
                    x={zx * 20} y={zy * 20}
                    width={20} height={20}
                    fill={isAccident ? 'rgba(239,68,68,0.06)' : 'rgba(249,115,22,0.06)'}
                    stroke={isAccident ? '#ef4444' : '#f97316'}
                    strokeWidth="0.5"
                    strokeDasharray="2,2"
                    rx="0.5"
                    className="animate-pulse"
                  />
                  {/* Caution Triangle Icon */}
                  <g transform={`translate(${zx * 20 + 3.5}, ${zy * 20 + 3.5})`}>
                    <polygon
                      points="0,-2 2,1.5 -2,1.5"
                      fill={isAccident ? '#ef4444' : '#f97316'}
                      stroke="#fff"
                      strokeWidth="0.2"
                    />
                    <text
                      y="1"
                      textAnchor="middle"
                      fill="#fff"
                      fontSize="2"
                      fontWeight="bold"
                    >
                      !
                    </text>
                  </g>
                </g>
              );
            })}

            {/* Signal Timing Throttle Overlay (blue = Oracle-controlled speed limit) */}
            {Object.entries(cityState.zone_speed_limits ?? {}).map(([key, mult]) => {
              const [zx, zy] = key.split(',').map(Number);
              const intensity = (1 - mult) * 0.5; // mult=0.3 → intensity=0.35
              return (
                <g key={`sig-${key}`}>
                  <rect
                    x={zx * 20} y={zy * 20}
                    width={20} height={20}
                    fill={`rgba(59,130,246,${intensity.toFixed(3)})`}
                    stroke="rgba(99,179,255,0.4)"
                    strokeWidth="0.4"
                    strokeDasharray="1.5,1"
                    rx="0.5"
                    className="transition-all duration-500"
                  />
                  <text
                    x={zx * 20 + 10} y={zy * 20 + 11}
                    textAnchor="middle"
                    fill="rgba(147,210,255,0.85)"
                    fontSize="2.5"
                    fontWeight="600"
                  >
                    {`${Math.round(mult * 100)}%`}
                  </text>
                </g>
              );
            })}

            {/* Charging Hubs */}
            {cityState.hubs.map(hub => (
              <g key={hub.id} className="transition-all duration-[500ms] ease-out" transform={`translate(${hub.x}, ${hub.y})`}>
                {hub.active ? (
                  <>
                    <circle r="8" className="city-hub-pulse fill-pink-500/10 stroke-pink-500/30 stroke-[0.2] animate-ping" />
                    <circle r="5" className="fill-pink-500/20 stroke-pink-500/50 stroke-[0.5]" />
                    <circle r="1.5" className="fill-pink-400" />
                  </>
                ) : (
                  <>
                    <circle r="6" className="fill-red-950/40 stroke-red-500/70 stroke-[0.7]" />
                    <line x1="-2.2" y1="-2.2" x2="2.2" y2="2.2" className="stroke-red-400/90 stroke-[0.8]" />
                    <line x1="2.2" y1="-2.2" x2="-2.2" y2="2.2" className="stroke-red-400/90 stroke-[0.8]" />
                  </>
                )}
                <g className="opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <rect x="-5" y="-8" width="10" height="3.5" rx="1" fill="#1e1e2d" />
                  <text y="-5.5" className={`text-[1.8px] ${hub.active ? 'fill-pink-200' : 'fill-slate-300'} font-mono font-bold`} textAnchor="middle">
                    {hub.active ? `$${hub.price.toFixed(2)}` : 'OFFLINE'}
                  </text>
                  <rect x="-5" y="4.5" width="10" height="3.5" rx="1" fill="#1e1e2d" />
                  <text y="7" className="text-[1.8px] fill-slate-300 font-mono" textAnchor="middle">Q:{hub.queue}</text>
                </g>
              </g>
            ))}

            {/* Traffic Agents — small amber diamonds */}
            {cityState.traffic.map(t => (
              <g key={t.id} transform={`translate(${t.x}, ${t.y})`} className="transition-all duration-[500ms] ease-linear">
                <polygon
                  points="0,-1.2 1.0,0 0,1.2 -1.0,0"
                  fill="rgba(251,191,36,0.7)"
                  stroke="rgba(251,191,36,0.4)"
                  strokeWidth="0.2"
                />
              </g>
            ))}

            {/* EV Resident Trails */}
            {showTrails && Object.entries(trails).map(([id, path]) => {
              if (path.length < 2) return null;
              const res = cityState.residents.find(r => r.id === id);
              const isCrit = res ? res.battery < 30 : false;
              const isSelected = !selectedResidentId || id === selectedResidentId;
              const baseColor = res?.charging ? '#4ade80' : (isCrit ? '#ef4444' : '#60a5fa');
              return (
                <g key={`trail-${id}`}>
                  {path.slice(1).map((pt, i) => {
                    const opacity = Math.max(0, (i / (path.length - 1)) * (isSelected ? 0.85 : 0.18));
                    const width = 0.1 + (i / (path.length - 1)) * 0.4;
                    return (
                      <line key={i} x1={path[i].x} y1={path[i].y} x2={pt.x} y2={pt.y}
                        stroke={baseColor} strokeWidth={width} opacity={opacity} strokeLinecap="round" />
                    );
                  })}
                </g>
              );
            })}

            {/* EV Residents */}
            {cityState.residents.map(res => {
              const isCrit = res.battery < 30;
              const isWaiting = res.state === 'waiting';
              const residentLabel = res.id.replace('res_', '');
              const isSelected = !selectedResidentId || res.id === selectedResidentId;
              let baseColor = '#60a5fa';
              if (res.charging) baseColor = '#4ade80';
              else if (isWaiting) baseColor = '#facc15';
              else if (isCrit) baseColor = '#ef4444';
              return (
                <g 
                  key={res.id} 
                  className="transition-all duration-[500ms] ease-linear cursor-pointer" 
                  transform={`translate(${res.x}, ${res.y})`} 
                  opacity={isSelected ? 1 : 0.22}
                  onMouseEnter={() => setHoveredResidentId(res.id)}
                  onMouseLeave={() => setHoveredResidentId(null)}
                >
                  {isSelected && selectedResidentId && <circle r="3.4" fill="none" className="stroke-cyan-300/70 stroke-[0.45] animate-pulse pointer-events-none" />}
                  {/* Invisible hit area for easier hovering */}
                  <circle r="6" fill="transparent" />

                  {/* Scale base size and ring according to vehicle type */}
                  {(() => {
                    const baseR = res.vehicle_type === 'truck' ? 2.5 : res.vehicle_type === 'suv' ? 1.8 : 1.2;
                    const ringR = baseR + 1.5;
                    return (
                      <g className="pointer-events-none">
                        <circle r={res.charging ? baseR + 0.4 : baseR} fill={baseColor} />
                        <g transform="rotate(-90)">
                          <circle r={ringR} fill="none" className="stroke-white/5 stroke-[0.4]" />
                          <circle r={ringR} fill="none" stroke={baseColor}
                            strokeDasharray={`${(res.battery / 100) * (2 * Math.PI * ringR)} 100`}
                            className="stroke-[0.5] transition-all duration-300" />
                        </g>
                      </g>
                    );
                  })()}
                  {showResidentIds && (
                    <g className="pointer-events-none">
                      <rect x="1.8" y="-4.5" width="5.5" height="3" rx="0.8" fill="rgba(8,8,16,0.85)" />
                      <text x="4.5" y="-2.3" className="text-[1.8px] fill-cyan-200 font-mono font-bold" textAnchor="middle">
                        {residentLabel}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Hover Tooltip Rendered On Top */}
            {hoveredResidentId && (() => {
              const res = cityState.residents.find(r => r.id === hoveredResidentId);
              if (!res) return null;
              return (
                <g className="pointer-events-none drop-shadow-2xl z-50" transform={`translate(${res.x}, ${res.y})`}>
                  <rect x="-9" y="-14" width="18" height="8.5" rx="1.5" fill="#1e1e2d" className="stroke-white/10 stroke-[0.3]" />
                  <text y="-9.5" className="text-[2.0px] fill-white font-mono font-bold" textAnchor="middle">{res.id} ({res.vehicle_type})</text>
                  <text y="-6.5" className="text-[1.6px] fill-slate-300 font-mono" textAnchor="middle">{res.battery_raw?.toFixed(1)} / {res.battery_capacity} kWh</text>
                </g>
              );
            })()}
          </svg>

          {!liveFeedEnabled && startMode === 'smooth' && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#0a0a10]/55 backdrop-blur-[2px]">
              <button
                onClick={() => setLiveFeedEnabled(true)}
                className="rounded-full border border-orange-400/40 bg-orange-500/20 px-5 py-2 text-sm font-semibold text-orange-200 transition-colors hover:bg-orange-500/30"
              >
                Start Live Simulation
              </button>
            </div>
          )}

          {/* City Oracle Chat */}
          <div className="absolute bottom-6 left-6 w-[360px] h-[450px] flex flex-col rounded-2xl border border-white/10 bg-black/40 backdrop-blur-xl shadow-[0_0_30px_rgba(0,0,0,0.5)] overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-orange-900/40 to-amber-900/40">
              <Bot className="w-5 h-5 text-orange-400" />
              <h3 className="text-sm font-semibold tracking-wide text-orange-100">City Oracle</h3>
              {isChatting && <Loader2 className="w-4 h-4 text-orange-400 animate-spin ml-auto" />}
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
              {chatMessages.length === 0 && (
                <p className="text-xs text-slate-600 italic m-auto text-center">
                  Ask the City Oracle about<br />traffic, charging demand, or trends…
                </p>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-lg ${msg.role === 'user' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-orange-500/20 text-orange-300 border border-orange-500/30'}`}>
                    {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>
                  <div className={`px-4 py-2.5 rounded-2xl max-w-[80%] text-sm shadow-md ${msg.role === 'user' ? 'bg-blue-600/20 text-blue-50 border border-blue-500/20 rounded-tr-none' : 'bg-white/5 text-slate-200 border border-white/5 rounded-tl-none'}`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <form onSubmit={sendMessage} className="p-3 border-t border-white/10 bg-black/40 flex gap-2">
              <input type="text" value={chatInput} onChange={e => setChatInput(e.target.value)}
                placeholder="Ask the City Oracle…"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-orange-500/50 transition-colors shadow-inner" />
              <button type="submit" disabled={isChatting || !chatInput.trim()}
                aria-label="Send message to City Oracle"
                title="Send"
                className="w-10 h-10 rounded-xl bg-orange-600/30 hover:bg-orange-600/50 flex items-center justify-center text-orange-300 disabled:opacity-50 transition-colors shadow-lg border border-orange-500/30">
                <Send className="w-4 h-4 ml-0.5" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-[340px] flex flex-col gap-6 overflow-y-auto">

          {/* Live City Metrics */}
          <div className="p-7 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl">
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-5 text-slate-400">Live Metrics</h2>
            <div className="flex flex-col gap-4">
              {[
                { label: 'EV Residents', value: cityState.residents.length, color: 'text-blue-400', Icon: Zap },
                { label: 'Traffic Agents', value: cityState.traffic.length, color: 'text-yellow-400', Icon: Car },
                { label: 'Charging Now', value: chargingCount, color: 'text-green-400', pulse: true, Icon: Activity },
                { label: 'Seeking Hub', value: seekingCount, color: 'text-orange-400', Icon: Radio },
                { label: 'Critical Battery', value: criticalCount, color: 'text-red-400', Icon: Zap },
              ].map(({ label, value, color, pulse, Icon }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {pulse && <div className={`w-2 h-2 rounded-full ${color.replace('text-', 'bg-')} animate-pulse`} />}
                    <Icon className={`w-3.5 h-3.5 ${color} opacity-60`} />
                    <p className="text-sm text-slate-400">{label}</p>
                  </div>
                  <p className={`text-2xl font-light tracking-tighter ${color}`}>{value}</p>
                </div>
              ))}
              <div className="h-px w-full bg-gradient-to-r from-white/5 to-transparent" />
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">Avg Congestion</p>
                <p className={`text-2xl font-light tracking-tighter ${maxCongestion > 0.7 ? 'text-red-400' : maxCongestion > 0.4 ? 'text-orange-400' : 'text-green-400'}`}>
                  {(avgCongestion * 100).toFixed(0)}%
                </p>
              </div>
              {cityState.metrics && (
                <>
                  <div className="h-px w-full bg-gradient-to-r from-white/5 to-transparent" />
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-slate-400">Grid Load (Total / EV)</p>
                    <p className="text-xs font-mono font-bold text-cyan-300">
                      {cityState.metrics.total_city_grid_load_kw} / {cityState.metrics.ev_power_demand_kw} kW
                    </p>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-slate-400">CO2 Saved (Displaced)</p>
                    <p className="text-xs font-mono font-bold text-emerald-400">
                      {cityState.metrics.co2_saved_kg_h} kg/h
                    </p>
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-slate-400">Avg Battery Health</p>
                    <p className="text-xs font-mono font-bold text-teal-400">
                      {(cityState.metrics.avg_fleet_soh * 100).toFixed(1)}% SOH
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Live Belgian Traffic Incidents Panel */}
          <div className="p-6 rounded-[2rem] border border-orange-500/10 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-orange-400">Flanders Traffic Feed</h2>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-[10px] font-medium border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Sync
              </div>
            </div>
            <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
              {!cityState.live_traffic_events || cityState.live_traffic_events.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No active traffic incidents detected in Flanders.</p>
              ) : (
                cityState.live_traffic_events.map((ev) => (
                  <div key={ev.id} className="p-3 rounded-xl border border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-colors flex gap-2">
                    <span className="text-xs mt-0.5 shrink-0">
                      {ev.event_type === 'accident' ? '🚨' : '🚗'}
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-semibold text-slate-200 uppercase">{ev.event_type}</p>
                        <span className="text-[10px] font-mono text-slate-500">Zone {ev.zone_key}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1 leading-normal">{ev.description}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <ProfitMarginWidget />

          <div className="min-h-[520px]">
            <CityScenarioLab apiBase={API_BASE} />
          </div>

          {/* EV Tracker */}
          <div className="p-6 rounded-[2rem] border border-cyan-500/10 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-cyan-300/80">EV Tracker</h2>
            <div className="flex gap-2">
              <input
                type="text"
                value={residentFilter}
                onChange={(e) => setResidentFilter(e.target.value)}
                placeholder="Search EV ID (e.g. 7)"
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-cyan-500/50"
              />
              <button
                onClick={() => setResidentFilter('')}
                className="px-3 py-2 rounded-xl border border-slate-500/30 bg-slate-500/10 text-slate-300 text-xs hover:bg-slate-500/20 transition-colors"
              >
                Clear
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {cityState.residents.slice(0, 10).map((r) => {
                const shortId = r.id.replace('res_', '');
                const active = selectedResidentId === r.id;
                return (
                  <button
                    key={r.id}
                    onClick={() => setResidentFilter(shortId)}
                    className={`px-2.5 py-1 rounded-full text-[11px] font-mono border transition-colors ${active ? 'border-cyan-400/70 bg-cyan-500/20 text-cyan-200' : 'border-white/10 bg-white/5 text-slate-400 hover:bg-white/10'}`}
                  >
                    {shortId}
                  </button>
                );
              })}
            </div>
            {selectedResident ? (
              <div className="mt-1 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs">
                <p className="font-mono text-cyan-200 mb-1">EV {selectedResident.id.replace('res_', '')} ({selectedResident.vehicle_type})</p>
                <p className="text-slate-300">State: <span className="text-slate-100 font-medium uppercase">{selectedResident.state}</span></p>
                <p className="text-slate-300">Battery: <span className="text-slate-100 font-medium">{selectedResident.battery.toFixed(1)}%</span> <span className="text-slate-500 font-mono">({selectedResident.battery_raw?.toFixed(1)}/{selectedResident.battery_capacity?.toFixed(1)}kWh)</span></p>
                <p className="text-slate-300">Health (SOH): <span className={`font-medium ${selectedResident.soh > 0.9 ? 'text-green-400' : selectedResident.soh > 0.8 ? 'text-yellow-400' : 'text-red-400'}`}>{(selectedResident.soh * 100).toFixed(1)}%</span></p>
                <p className="text-slate-300">Physics: <span className="text-slate-100 font-medium">{cityState.weather === 'extreme_cold' ? '❄️ Coldgate Active' : cityState.weather === 'extreme_heat' ? '🔥 Thermal Throttled' : '✅ Nominal'}</span></p>
                <p className="text-slate-300">Drag/Regen: <span className="text-slate-100 font-medium">{selectedResident.aero_drag?.toFixed(3)} kW / {(selectedResident.regen_efficiency * 100).toFixed(0)}%</span></p>
                <p className="text-slate-300">Temp/Payload: <span className="text-slate-100 font-medium">{selectedResident.battery_temperature?.toFixed(1)}°C / {selectedResident.payload_weight?.toFixed(0)} kg</span></p>
                <p className="text-slate-300">Position: <span className="text-slate-100 font-mono">({selectedResident.x.toFixed(1)}, {selectedResident.y.toFixed(1)})</span></p>
              </div>
            ) : normalizedResidentFilter ? (
              <p className="text-xs text-amber-300/80">No EV match for this filter.</p>
            ) : (
              <p className="text-xs text-slate-500">Select an EV ID to focus its path and live status.</p>
            )}
          </div>

          {/* Agent Hierarchy */}
          <div className="p-6 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-4">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Multi-Agent Hierarchy</h2>
            {/* Tier indicators */}
            {[
              { tier: 'Scout', color: 'text-sky-400 border-sky-500/30 bg-sky-500/10', desc: 'EVScout + TrafficScout · every tick' },
              { tier: 'Analyzer', color: 'text-violet-400 border-violet-500/30 bg-violet-500/10', desc: 'Demand + Congestion · rolling window' },
              { tier: 'Chief Oracle', color: 'text-orange-400 border-orange-500/30 bg-orange-500/10', desc: 'Rule-based synthesis · every 30 ticks' },
            ].map(({ tier, color, desc }) => (
              <div key={tier} className={`flex items-start gap-3 p-3 rounded-xl border ${color}`}>
                <div className={`w-2 h-2 rounded-full mt-1.5 ${color.replace('text-', 'bg-')} animate-pulse shrink-0`} />
                <div>
                  <p className={`text-sm font-semibold ${color}`}>{tier}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Policy Dashboard */}
          <div className="min-h-[760px]">
            <PolicyDashboard 
              decisions={decisions} 
              cityState={cityState}
              forecast={forecast}
              segments={segments}
              recommendations={recommendations}
              oracleMode={oracleMode}
              onToggleMode={toggleOracleMode}
              telemetryHistory={telemetry}
            />
          </div>

          {/* Hub Markets */}
          <div className="p-6 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl">
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-4 text-slate-400">Hub Markets</h2>
            <div className="space-y-2">
              {cityState.hubs.map(hub => {
                const prev = prevHubPricesRef.current[hub.id];
                const delta = prev == null ? 0 : hub.price - prev;
                prevHubPricesRef.current[hub.id] = hub.price;
                const waiting = hub.waiting ?? hub.queue ?? 0;
                const chargingUsed = hub.charging ?? hub.slots_used ?? 0;
                const capacity = hub.capacity ?? 0;
                return (
                  <div key={hub.id} className={`flex justify-between items-center p-3 rounded-xl border transition-colors ${hub.active ? 'bg-white/[0.02] border-white/5' : 'bg-red-950/20 border-red-900/30'}`}>
                    <div>
                      <p className={`text-sm font-medium ${hub.active ? 'text-slate-200' : 'text-red-400/80'}`}>
                        {hub.id.toUpperCase()}{!hub.active && ' (OFFLINE)'}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 font-mono">
                        Waiting:{waiting} • Charging:{chargingUsed}/{capacity || 0}
                      </p>
                    </div>
                    {hub.active ? (
                      <div className="text-right font-mono">
                        <p className="text-base text-pink-300">
                          ${hub.price.toFixed(3)}
                          <span className="text-xs text-pink-500/50">/kWh</span>
                        </p>
                        <p className={`text-[10px] ${delta > 0 ? 'text-red-300' : delta < 0 ? 'text-green-300' : 'text-slate-500'}`}>
                          {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-red-500/50 font-mono uppercase tracking-wider">Offline</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Historical Trends */}
          <div className="min-h-[390px] p-6 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl">
            <h2 className="text-xs font-semibold uppercase tracking-widest mb-4 text-slate-400">Historical Trends</h2>
            {telemetry.length < 2 ? (
              <div className="animate-pulse space-y-3">
                <p className="text-xs text-slate-600 italic">Collecting data…</p>
                <div className="h-10 rounded-xl bg-white/5" />
                <div className="h-10 rounded-xl bg-white/5" />
                <div className="h-10 rounded-xl bg-white/5" />
                <div className="h-10 rounded-xl bg-white/5" />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Avg Price ($/kWh)</p>
                  <Sparkline values={priceHistory} color="#f472b6" />
                  <div className="flex justify-between text-[10px] text-slate-600 mt-0.5 font-mono">
                    <span>${Math.min(...priceHistory).toFixed(2)}</span>
                    <span>${Math.max(...priceHistory).toFixed(2)}</span>
                  </div>
                </div>
                <div className="h-px w-full bg-gradient-to-r from-white/5 to-transparent" />
                <div>
                  <p className="text-xs text-slate-500 mb-1">Total Queue Length</p>
                  <Sparkline values={queueHistory} color="#fb923c" />
                  <div className="flex justify-between text-[10px] text-slate-600 mt-0.5 font-mono">
                    <span>{Math.min(...queueHistory)}</span>
                    <span>{Math.max(...queueHistory)}</span>
                  </div>
                </div>
                <div className="h-px w-full bg-gradient-to-r from-white/5 to-transparent" />
                <div>
                  <p className="text-xs text-slate-500 mb-1">Avg Battery Temp (°C)</p>
                  <Sparkline values={tempHistory} color="#ef4444" />
                  <div className="flex justify-between text-[10px] text-slate-600 mt-0.5 font-mono">
                    <span>{Math.min(...tempHistory).toFixed(1)}</span>
                    <span>{Math.max(...tempHistory).toFixed(1)}</span>
                  </div>
                </div>
                <div className="h-px w-full bg-gradient-to-r from-white/5 to-transparent" />
                <div>
                  <p className="text-xs text-slate-500 mb-1">Avg Aero Drag (kW)</p>
                  <Sparkline values={dragHistory} color="#8b5cf6" />
                  <div className="flex justify-between text-[10px] text-slate-600 mt-0.5 font-mono">
                    <span>{Math.min(...dragHistory).toFixed(3)}</span>
                    <span>{Math.max(...dragHistory).toFixed(3)}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
