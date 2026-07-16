'use client';

import { useState } from 'react';
import { Activity, ShieldAlert, Thermometer, Settings, ArrowRight } from 'lucide-react';

type Decision = {
  agent: string;
  type: string;
  description: string;
  confidence: number;
  tick: number | null;
  at: string;
};

type CityState = {
  weather?: string;
  zone_congestion: Record<string, number>;
  zone_speed_limits: Record<string, number>;
  traffic_incident_speed_limits?: Record<string, number>;
};

type TelemetryRow = {
  timestamp: string;
  weather?: string;
  active_hubs: number;
  avg_price: number;
  total_queue: number;
  avg_temp?: number;
  avg_drag?: number;
};

type SegmentDetails = { count: number; ratio: number };
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
  demand_risk_band: string;
};

const DECISION_COLORS: Record<string, string> = {
  demand_response: 'bg-blue-500/20 text-blue-300 border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]',
  capacity_expansion: 'bg-purple-500/20 text-purple-300 border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.15)]',
  traffic_rerouting: 'bg-orange-500/20 text-orange-300 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.15)]',
  status_nominal: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.15)]',
};

function ratioToWidthClass(ratio: number) {
  if (ratio <= 0.02) return 'w-0';
  if (ratio <= 0.125) return 'w-[12.5%]';
  if (ratio <= 0.25) return 'w-1/4';
  if (ratio <= 0.375) return 'w-[37.5%]';
  if (ratio <= 0.5) return 'w-1/2';
  if (ratio <= 0.625) return 'w-[62.5%]';
  if (ratio <= 0.75) return 'w-3/4';
  if (ratio <= 0.875) return 'w-[87.5%]';
  return 'w-full';
}

export default function PolicyDashboard({ 
  decisions, 
  cityState,
  segments,
  recommendations = [],
  oracleMode,
  onToggleMode,
  telemetryHistory = []
}: { 
  decisions: Decision[], 
  cityState: CityState,
  forecast?: unknown,
  segments?: SegmentData | null,
  recommendations?: string[],
  oracleMode?: 'advisor' | 'autopilot',
  onToggleMode?: () => void,
  telemetryHistory?: TelemetryRow[]
}) {
  const manualThrottled = Object.entries(cityState.zone_speed_limits).filter(([, mult]) => mult < 1.0);
  const incidentThrottled = Object.entries(cityState.traffic_incident_speed_limits ?? {}).filter(([, mult]) => mult < 1.0);
  const activeSpeedLimits = Array.from(new Set([
    ...manualThrottled.map(([zone]) => zone),
    ...incidentThrottled.map(([zone]) => zone),
  ]));
  const avgCongestion = Object.values(cityState.zone_congestion).reduce((a, b) => a + b, 0) / (Object.values(cityState.zone_congestion).length || 1);
  const criticalRatio = segments?.battery_segments?.battery_critical?.ratio || 0;
  const lowRatio = segments?.battery_segments?.battery_low?.ratio || 0;
  const midRatio = segments?.battery_segments?.battery_mid?.ratio || 0;
  const highRatio = segments?.battery_segments?.battery_high?.ratio || 0;

  const [selectedDecision, setSelectedDecision] = useState<Decision | null>(null);

  return (
    <div className="p-7 rounded-[2rem] border border-orange-500/20 bg-gradient-to-b from-[#12121a]/90 to-[#0a0a10]/95 backdrop-blur-2xl shadow-[0_0_40px_rgba(234,88,12,0.06)] flex flex-col gap-6 relative overflow-hidden group transition-all duration-700 hover:shadow-[0_0_50px_rgba(234,88,12,0.12)]">
      {/* Decorative Glows */}
      <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-orange-500/10 blur-[100px] rounded-full mix-blend-screen pointer-events-none opacity-40 group-hover:opacity-100 transition-opacity duration-1000" />
      <div className="absolute bottom-0 left-0 w-[200px] h-[200px] bg-blue-500/10 blur-[80px] rounded-full mix-blend-screen pointer-events-none opacity-40 group-hover:opacity-100 transition-opacity duration-1000" />

      {/* Header */}
      <div className="flex justify-between items-center relative z-10">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-widest text-orange-400 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" /> Policy Dashboard
          </h2>
          <p className="text-xs text-slate-500 mt-1">Global Constraints & Oracle Reasoning</p>
        </div>
        <div className="flex items-center gap-3">
          {oracleMode && onToggleMode && (
            <div className="flex items-center gap-2 mr-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Advisor</span>
              <button 
                type="button"
                role="switch"
                aria-checked={oracleMode === 'autopilot' ? 'true' : 'false'}
                aria-label="Toggle Oracle Autopilot"
                onClick={onToggleMode}
                className="w-10 h-5 rounded-full p-0.5 transition-all relative border border-white/5 cursor-pointer"
                style={{
                  backgroundColor: oracleMode === 'autopilot' ? 'rgba(249, 115, 22, 0.2)' : '#1e293b'
                }}
              >
                <div 
                  className="w-4 h-4 rounded-full transition-all shadow-md"
                  style={{
                    backgroundColor: oracleMode === 'autopilot' ? '#fb923c' : '#f97316',
                    transform: oracleMode === 'autopilot' ? 'translateX(20px)' : 'translateX(0px)'
                  }}
                />
              </button>
              <span className="text-[10px] font-bold uppercase tracking-widest text-orange-400">Autopilot</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 relative z-10">
        {/* Active Constraints */}
        <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex flex-col gap-4">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-orange-400" /> Active Constraints
          </h3>
          <div className="flex flex-col gap-3.5 mt-1.5">
            {/* Speed Limits */}
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400 font-light">Traffic Restrictions</span>
              <span className="text-xs font-mono font-medium text-slate-300">
                {activeSpeedLimits.length > 0 ? `${activeSpeedLimits.length} zone(s) throttled` : 'None'}
              </span>
            </div>
            {/* Fleet Congestion */}
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400 font-light">Avg City Congestion</span>
              <span className={`text-xs font-mono font-semibold ${avgCongestion > 0.4 ? 'text-red-400' : avgCongestion > 0.2 ? 'text-orange-400' : 'text-slate-300'}`}>
                {(avgCongestion * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        {/* Battery Health Segments */}
        <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex flex-col gap-3.5">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <Thermometer className="w-3.5 h-3.5 text-orange-400" /> Battery Health Status
          </h3>
          {segments ? (
            <div className="flex flex-col gap-2 mt-1.5">
              <div className="flex w-full h-1.5 rounded-full overflow-hidden bg-slate-800 border border-white/5">
                <div className={`${ratioToWidthClass(criticalRatio)} bg-red-500 transition-all`} />
                <div className={`${ratioToWidthClass(lowRatio)} bg-amber-500 transition-all`} />
                <div className={`${ratioToWidthClass(midRatio)} bg-yellow-500 transition-all`} />
                <div className={`${ratioToWidthClass(highRatio)} bg-emerald-500 transition-all`} />
              </div>
              <div className="flex justify-between text-[9px] font-mono text-slate-500 mt-1 uppercase tracking-wider font-semibold">
                <span className="text-red-400">Crit {(criticalRatio * 100).toFixed(0)}%</span>
                <span className="text-amber-400">Low {(lowRatio * 100).toFixed(0)}%</span>
                <span className="text-yellow-400">Mid {(midRatio * 100).toFixed(0)}%</span>
                <span className="text-emerald-400">High {(highRatio * 100).toFixed(0)}%</span>
              </div>
            </div>
          ) : (
            <div className="h-6 flex items-center text-xs text-slate-500 italic mt-1 pl-1">Analyzing battery segments…</div>
          )}
        </div>
      </div>

      {/* Target Segment Insights */}
      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex flex-col gap-3 relative z-10">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 flex items-center gap-2">
          <Settings className="w-3.5 h-3.5 text-orange-400" /> Segment Insights
        </h3>
        {segments ? (
          <div className="flex justify-between items-center mt-1">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-slate-300 font-light pl-0.5">Demand Risk</span>
            </div>
            <div className="flex items-center gap-4">
              <span className={`text-xs font-mono uppercase font-bold ${segments.demand_risk_band === 'high' ? 'text-red-400' : segments.demand_risk_band === 'medium' ? 'text-orange-400' : 'text-emerald-400'}`}>
                {segments.demand_risk_band}
              </span>
              <div className="flex gap-1.5 items-center bg-black/40 border border-white/5 rounded-xl px-3 py-1.5">
                <div className={`w-2.5 h-2.5 rounded-sm ${segments.demand_risk_band === 'high' ? 'bg-red-500 animate-pulse' : segments.demand_risk_band === 'medium' ? 'bg-orange-500' : 'bg-emerald-500'}`} />
                <div className={`w-2.5 h-2.5 rounded-sm ${segments.demand_risk_band === 'high' ? 'bg-red-500' : segments.demand_risk_band === 'medium' ? 'bg-orange-500' : 'bg-slate-800'}`} />
                <div className={`w-2.5 h-2.5 rounded-sm ${segments.demand_risk_band === 'high' ? 'bg-red-500' : 'bg-slate-800'}`} />
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500 italic py-1 pl-1">Awaiting segment metrics…</div>
        )}
      </div>

      {/* Recommended Actions */}
      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02] flex flex-col gap-3.5 relative z-10">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Recommended Actions Queue</h3>
        {recommendations.length > 0 ? (
          <div className="flex flex-col gap-2.5 mt-1">
            {recommendations.map((rec, idx) => (
              <div key={idx} className="flex gap-3 text-xs text-slate-300 leading-relaxed font-light border border-white/5 bg-white/[0.01] hover:bg-white/[0.03] transition-colors p-3.5 rounded-xl">
                <ArrowRight className="w-4 h-4 mt-0.5 text-orange-400 shrink-0" />
                <span className="font-light">{rec}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-xs text-slate-500">No recommendations queued yet.</div>
        )}
      </div>

      {/* Decisions Feed */}
      <div className="flex flex-col relative z-10 mt-2">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 pl-1">Oracle Synthesis Feed</h3>
        </div>
        {decisions.length === 0 ? (
          <div className="p-6 rounded-2xl border border-white/5 bg-white/[0.02] flex items-center justify-center">
            <p className="text-xs text-slate-500 italic flex items-center gap-2">
              <Activity className="w-4 h-4 animate-pulse" /> Awaiting oracle synthesis…
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {decisions.slice(-5).reverse().map((d, i) => (
              <div 
                key={i} 
                className="p-4 rounded-2xl border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent hover:bg-white/[0.06] hover:border-orange-500/20 transition-all group/item hover:-translate-y-0.5 cursor-pointer shadow-sm hover:shadow-xl"
                onClick={() => setSelectedDecision(d)}
              >
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded-full border ${DECISION_COLORS[d.type] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30'}`}>
                      {d.type.replace(/_/g, ' ')}
                    </span>
                    {d.agent && <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">{d.agent}</span>}
                  </div>
                  {d.confidence != null && (
                    <span className={`flex items-center gap-1.5 text-[11px] font-mono font-medium px-2 py-1 rounded-lg bg-black/40 border border-white/5 ${d.confidence > 0.8 ? 'text-emerald-400' : 'text-amber-400'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${d.confidence > 0.8 ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                      {(d.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed font-light pl-1">{d.description}</p>
                
                {/* Micro-interaction expansion hint */}
                <div className="mt-3 pl-1 flex items-center gap-1.5 opacity-0 group-hover/item:opacity-100 transition-all duration-300 translate-x-[-10px] group-hover/item:translate-x-0">
                  <ArrowRight className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-orange-400/90">View Correlated Telemetry</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Telemetry Correlation Modal */}
      {selectedDecision && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-all animate-fade-in"
          onClick={() => setSelectedDecision(null)}
        >
          <div 
            className="w-full max-w-md p-6 rounded-3xl border border-orange-500/30 bg-[#0e0e15] shadow-2xl flex flex-col gap-4 relative animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start">
              <div>
                <span className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded-full border ${DECISION_COLORS[selectedDecision.type] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30'}`}>
                  {selectedDecision.type.replace(/_/g, ' ')}
                </span>
                <h3 className="text-sm font-semibold text-slate-200 mt-2">Correlated Telemetry Metrics</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">Tick {selectedDecision.tick ?? 'N/A'} · {new Date(selectedDecision.at).toLocaleTimeString()}</p>
              </div>
              <button 
                type="button"
                className="text-slate-400 hover:text-slate-200 text-sm font-semibold bg-white/5 w-8 h-8 rounded-full flex items-center justify-center border border-white/5 hover:bg-white/10 transition-colors cursor-pointer"
                onClick={() => setSelectedDecision(null)}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>
            
            <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 text-xs text-slate-300 leading-relaxed font-light mb-2">
              <strong>Oracle Reason:</strong> {selectedDecision.description}
            </div>

            <div className="grid grid-cols-2 gap-3">
              {(() => {
                const targetTime = new Date(selectedDecision.at).getTime();
                let closestRow = telemetryHistory && telemetryHistory.length > 0 ? telemetryHistory[0] : null;
                if (closestRow) {
                  let minDiff = Math.abs(new Date(closestRow.timestamp).getTime() - targetTime);
                  for (const row of telemetryHistory) {
                    const diff = Math.abs(new Date(row.timestamp).getTime() - targetTime);
                    if (diff < minDiff) {
                      minDiff = diff;
                      closestRow = row;
                    }
                  }
                }
                
                if (!closestRow) {
                  return (
                    <div className="col-span-2 text-center py-4 text-xs text-slate-500">
                      No matching historical telemetry captured in browser session.
                    </div>
                  );
                }

                return (
                  <>
                    <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Weather</span>
                      <span className="text-xs font-medium text-slate-300 capitalize">{closestRow.weather ?? 'unknown'}</span>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Active Hubs</span>
                      <span className="text-xs font-mono font-medium text-slate-300">{closestRow.active_hubs}</span>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Average Price</span>
                      <span className="text-xs font-mono font-medium text-orange-400">€{closestRow.avg_price?.toFixed(3)}/kWh</span>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                      <span className="text-[10px] text-slate-500 uppercase font-semibold">Total Queue</span>
                      <span className="text-xs font-mono font-medium text-slate-300">{closestRow.total_queue} residents</span>
                    </div>
                    {closestRow.avg_temp != null && (
                      <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold">Fleet Temp</span>
                        <span className="text-xs font-mono font-medium text-slate-300">{closestRow.avg_temp.toFixed(1)}°C</span>
                      </div>
                    )}
                    {closestRow.avg_drag != null && (
                      <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/5 flex flex-col gap-1">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold">Avg Aero Drag</span>
                        <span className="text-xs font-mono font-medium text-slate-300">{closestRow.avg_drag.toFixed(2)}</span>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
