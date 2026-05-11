'use client';

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
};

const DECISION_COLORS: Record<string, string> = {
  demand_response: 'bg-blue-500/20 text-blue-300 border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]',
  capacity_expansion: 'bg-purple-500/20 text-purple-300 border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.15)]',
  traffic_rerouting: 'bg-orange-500/20 text-orange-300 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.15)]',
  status_nominal: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.15)]',
};

export default function PolicyDashboard({ 
  decisions, 
  cityState,
  forecast,
  segments,
  recommendations = [],
  oracleMode,
  onToggleMode
}: { 
  decisions: Decision[], 
  cityState: CityState,
  forecast?: any,
  segments?: any,
  recommendations?: string[],
  oracleMode?: 'advisor' | 'autopilot',
  onToggleMode?: () => void
}) {
  const activeSpeedLimits = Object.entries(cityState.zone_speed_limits).filter(([_, mult]) => mult < 1.0);
  const avgCongestion = Object.values(cityState.zone_congestion).reduce((a, b) => a + b, 0) / (Object.values(cityState.zone_congestion).length || 1);

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
                onClick={onToggleMode}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none shadow-inner ${oracleMode === 'autopilot' ? 'bg-orange-500 shadow-[0_0_10px_rgba(249,115,22,0.4)]' : 'bg-slate-700/80'}`}
              >
                <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${oracleMode === 'autopilot' ? 'translate-x-4.5' : 'translate-x-1'}`} style={{ transform: oracleMode === 'autopilot' ? 'translateX(18px)' : 'translateX(4px)' }} />
              </button>
              <span className={`text-[10px] font-bold uppercase tracking-widest ${oracleMode === 'autopilot' ? 'text-orange-400' : 'text-slate-500'}`}>Autopilot</span>
            </div>
          )}
          <span className="flex h-2.5 w-2.5 relative" title={`Mode: ${oracleMode?.toUpperCase() || 'UNKNOWN'}`}>
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${oracleMode === 'autopilot' ? 'bg-orange-400' : 'bg-blue-400'}`} />
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 shadow-[0_0_10px_rgba(245,158,11,0.6)] ${oracleMode === 'autopilot' ? 'bg-gradient-to-r from-orange-400 to-amber-500' : 'bg-gradient-to-r from-blue-400 to-cyan-500'}`} />
          </span>
        </div>
      </div>

      {/* Constraints Grid */}
      <div className="grid grid-cols-2 gap-3 relative z-10">
        <div className="rounded-2xl border border-white/5 bg-black/40 p-4 shadow-inner hover:bg-white/[0.04] transition-colors duration-300">
          <div className="flex items-center gap-2 mb-2">
            <Thermometer className="w-4 h-4 text-rose-400 opacity-80" />
            <p className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Thermal</p>
          </div>
          <p className={`text-base font-semibold capitalize tracking-tight ${cityState.weather === 'extreme_cold' ? 'text-cyan-300' : cityState.weather === 'extreme_heat' ? 'text-rose-400' : 'text-emerald-300'}`}>
            {cityState.weather ? cityState.weather.replace(/_/g, ' ') : 'Nominal'}
          </p>
        </div>
        <div className="rounded-2xl border border-white/5 bg-black/40 p-4 shadow-inner hover:bg-white/[0.04] transition-colors duration-300">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-cyan-400 opacity-80" />
            <p className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Network Load</p>
          </div>
          <p className={`text-base font-semibold tracking-tight ${avgCongestion > 0.5 ? 'text-orange-400' : 'text-emerald-400'}`}>
            {(avgCongestion * 100).toFixed(1)}% Congested
          </p>
        </div>
      </div>

      {/* Dynamic Throttle Module */}
      {activeSpeedLimits.length > 0 && (
        <div className="rounded-2xl border border-blue-500/20 bg-blue-500/[0.03] p-4 relative z-10 shadow-[inset_0_0_20px_rgba(59,130,246,0.05)]">
          <div className="flex items-center gap-2 mb-3">
            <Settings className="w-4 h-4 text-blue-400 animate-[spin_6s_linear_infinite]" />
            <p className="text-[10px] uppercase tracking-wider text-blue-300 font-semibold">Active Traffic Throttle</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeSpeedLimits.slice(0, 4).map(([zone, limit]) => (
              <div key={zone} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                <span className="text-[11px] text-blue-200 font-mono">
                  Zone {zone}: {Math.round(limit * 100)}%
                </span>
              </div>
            ))}
            {activeSpeedLimits.length > 4 && (
               <span className="px-2.5 py-1 rounded-full bg-blue-500/5 border border-blue-500/10 text-[11px] text-blue-300 font-mono">
                 +{activeSpeedLimits.length - 4} more
               </span>
            )}
          </div>
        </div>
      )}

      {/* Forecast Strip */}
      {forecast && (
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03] p-4 relative z-10 shadow-[inset_0_0_20px_rgba(16,185,129,0.05)]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <p className="text-[10px] uppercase tracking-wider text-emerald-300 font-semibold">Oracle Forecast ({forecast.horizon_ticks} Ticks)</p>
            </div>
            <span className="text-[10px] font-mono text-emerald-400/80">Conf: {(forecast.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="bg-black/30 rounded-xl p-2.5 border border-white/5">
              <span className="text-[10px] text-slate-400 block mb-1 uppercase">Proj. Queue</span>
              <span className="font-mono text-emerald-200">{forecast.projected_total_queue}</span>
            </div>
            <div className="bg-black/30 rounded-xl p-2.5 border border-white/5">
              <span className="text-[10px] text-slate-400 block mb-1 uppercase">Proj. Price</span>
              <span className="font-mono text-emerald-200">${forecast.projected_avg_price.toFixed(3)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Segment Insights */}
      {segments && (
        <div className="rounded-2xl border border-purple-500/20 bg-purple-500/[0.03] p-4 relative z-10 shadow-[inset_0_0_20px_rgba(168,85,247,0.05)]">
          <div className="flex items-center gap-2 mb-3">
            <Settings className="w-4 h-4 text-purple-400" />
            <p className="text-[10px] uppercase tracking-wider text-purple-300 font-semibold">Segment Insights</p>
          </div>
          <div className="flex justify-between items-center bg-black/30 rounded-xl p-2.5 border border-white/5 mb-2">
            <span className="text-xs text-slate-300">Demand Risk</span>
            <span className={`text-xs font-mono uppercase font-bold ${segments.demand_risk_band === 'high' ? 'text-red-400' : segments.demand_risk_band === 'medium' ? 'text-orange-400' : 'text-emerald-400'}`}>
              {segments.demand_risk_band}
            </span>
          </div>
          <div className="grid grid-cols-4 gap-1 h-2 rounded-full overflow-hidden bg-white/10 mt-2">
             <div style={{width: `${(segments.battery_segments?.battery_critical?.ratio || 0) * 100}%`}} className="bg-red-500 h-full" title="Critical" />
             <div style={{width: `${(segments.battery_segments?.battery_low?.ratio || 0) * 100}%`}} className="bg-orange-500 h-full" title="Low" />
             <div style={{width: `${(segments.battery_segments?.battery_mid?.ratio || 0) * 100}%`}} className="bg-yellow-500 h-full" title="Mid" />
             <div style={{width: `${(segments.battery_segments?.battery_high?.ratio || 0) * 100}%`}} className="bg-green-500 h-full" title="High" />
          </div>
          <div className="flex justify-between text-[9px] text-slate-500 mt-1 uppercase">
            <span>Critical</span><span>High</span>
          </div>
        </div>
      )}

      {/* Recommended Actions Queue */}
      {recommendations && recommendations.length > 0 && (
        <div className="flex flex-col relative z-10 mt-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-orange-400 pl-1">Recommended Actions Queue</h3>
          </div>
          <div className="space-y-2">
            {recommendations.map((rec, idx) => (
              <div key={idx} className="p-3 rounded-xl border border-orange-500/30 bg-orange-500/10 text-orange-200 text-sm flex items-start gap-3 shadow-sm">
                <ArrowRight className="w-4 h-4 mt-0.5 text-orange-400 shrink-0" />
                <span className="font-light">{rec}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
              <div key={i} className="p-4 rounded-2xl border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent hover:bg-white/[0.06] transition-all group/item hover:-translate-y-0.5 cursor-default shadow-sm hover:shadow-xl">
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
    </div>
  );
}
