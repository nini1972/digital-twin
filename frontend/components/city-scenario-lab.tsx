'use client';

import { useEffect, useMemo, useState } from 'react';
import { FlaskConical, Loader2, Play, RotateCcw, ShieldCheck } from 'lucide-react';

type ScenarioSchemaResponse = {
  endpoint: string;
  purpose: string;
  simulate_scenario: {
    horizon_ticks: { min: number; max: number; default: number };
    runs: { min: number; max: number; default: number };
    max_actions: number;
    supported_action_types: string[];
  };
  actions: Record<string, { example: Record<string, unknown> }>;
};

interface TrajectoryDataPoint {
  total_queue: number;
  avg_price: number;
  avg_congestion: number;
  active_hubs: number;
}

type ScenarioRunResult = {
  status: string;
  recommendation?: string;
  delta?: Record<string, number>;
  applied_actions?: Array<Record<string, unknown>>;
  validation_errors?: string[];
  safety?: { mutates_live_state?: boolean };
  baseline?: { trajectory?: TrajectoryDataPoint[] };
  scenario?: { trajectory?: TrajectoryDataPoint[] };
};

type Props = {
  apiBase: string;
};

const DEFAULT_ACTIONS = [
  { type: 'set_weather', weather: 'storm' },
  { type: 'rebalance_hub_load', strategy: 'hybrid', zone: '1,2', max_actions: 3, aggressiveness: 0.7 },
];

function formatActionLabel(actionType: string) {
  return actionType.replace(/_/g, ' ');
}

function TrajectoryChart({ baseline, scenario, metric, color, label }: { baseline: TrajectoryDataPoint[]; scenario: TrajectoryDataPoint[]; metric: keyof TrajectoryDataPoint; color: string; label: string }) {
  if (!baseline?.length || !scenario?.length) return null;
  const values = [...baseline, ...scenario].map(d => d[metric] as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 260;
  const h = 40;
  
  const getPts = (data: TrajectoryDataPoint[]) => data.map((d, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((d[metric] - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="mt-4">
      <div className="flex justify-between items-center mb-1">
        <p className="text-xs text-slate-500">{label}</p>
        <div className="flex gap-2 text-[10px]">
           <span className="text-slate-500 flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-slate-600"/> Baseline</span>
           <span className="text-emerald-300 flex items-center gap-1"><div className="w-2 h-2 rounded-full" style={{backgroundColor: color}}/> Scenario</span>
        </div>
      </div>
      <div className="relative">
        <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="overflow-visible">
          <polyline points={getPts(baseline)} fill="none" stroke="#475569" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.6" strokeDasharray="4 4" />
          <polyline points={getPts(scenario)} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

export default function CityScenarioLab({ apiBase }: Props) {
  const [schema, setSchema] = useState<ScenarioSchemaResponse | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [scenarioInput, setScenarioInput] = useState('');
  const [horizonTicks, setHorizonTicks] = useState(30);
  const [runs, setRuns] = useState(3);
  const [result, setResult] = useState<ScenarioRunResult | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadSchema = async () => {
      setIsLoadingSchema(true);
      setSchemaError(null);
      try {
        const response = await fetch(`${apiBase}/city/scenario/schema`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: ScenarioSchemaResponse = await response.json();
        if (cancelled) return;
        setSchema(data);
        setHorizonTicks(data.simulate_scenario.horizon_ticks.default);
        setRuns(data.simulate_scenario.runs.default);
      } catch (error) {
        if (!cancelled) {
          setSchemaError(String(error));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSchema(false);
        }
      }
    };

    loadSchema();
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const exampleActions = useMemo(() => {
    if (!schema) {
      return DEFAULT_ACTIONS;
    }
    return Object.values(schema.actions)
      .map((entry) => entry.example)
      .slice(0, 6);
  }, [schema]);

  useEffect(() => {
    if (!scenarioInput.trim()) {
      setScenarioInput(JSON.stringify(exampleActions.slice(0, 2), null, 2));
    }
  }, [exampleActions, scenarioInput]);

  const appendExample = (action: Record<string, unknown>) => {
    try {
      const parsed = scenarioInput.trim() ? JSON.parse(scenarioInput) : [];
      const list = Array.isArray(parsed) ? parsed : [parsed];
      setScenarioInput(JSON.stringify([...list, action], null, 2));
    } catch {
      setScenarioInput(JSON.stringify([action], null, 2));
    }
  };

  const resetScenario = () => {
    setScenarioInput(JSON.stringify(exampleActions.slice(0, 2), null, 2));
    setResult(null);
  };

  const runScenario = async () => {
    setIsRunning(true);
    setResult(null);

    try {
      const parsed = JSON.parse(scenarioInput);
      const scenarioActions = Array.isArray(parsed) ? parsed : [parsed];
      const response = await fetch(`${apiBase}/city/scenario/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_actions: scenarioActions,
          horizon_ticks: horizonTicks,
          runs,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: ScenarioRunResult = await response.json();
      setResult(data);
    } catch (error) {
      setResult({
        status: 'error',
        validation_errors: [String(error)],
      });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="p-6 rounded-[2rem] border border-emerald-500/10 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-emerald-300/80">Scenario Lab</h2>
          <p className="mt-1 text-xs text-slate-500">Copy-only what-if control plane for City Oracle actions.</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-[11px] text-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5" />
          Safe Sim
        </div>
      </div>

      <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
        {isLoadingSchema ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading scenario schema…
          </div>
        ) : schemaError ? (
          <p className="text-xs text-red-300/80">Schema error: {schemaError}</p>
        ) : schema ? (
          <>
            <div className="flex flex-wrap gap-2">
              {schema.simulate_scenario.supported_action_types.map((actionType) => (
                <span
                  key={actionType}
                  className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-mono text-slate-300"
                >
                  {formatActionLabel(actionType)}
                </span>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {exampleActions.map((action, index) => (
                <button
                  key={`${String(action.type)}-${index}`}
                  onClick={() => appendExample(action)}
                  className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-[11px] text-emerald-200 transition-colors hover:bg-emerald-500/20"
                >
                  + {formatActionLabel(String(action.type))}
                </button>
              ))}
            </div>
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs text-slate-400">
          Horizon Ticks
          <input
            type="number"
            min={schema?.simulate_scenario.horizon_ticks.min ?? 5}
            max={schema?.simulate_scenario.horizon_ticks.max ?? 120}
            value={horizonTicks}
            onChange={(event) => setHorizonTicks(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
          />
        </label>
        <label className="text-xs text-slate-400">
          Monte Carlo Runs
          <input
            type="number"
            min={schema?.simulate_scenario.runs.min ?? 1}
            max={schema?.simulate_scenario.runs.max ?? 10}
            value={runs}
            onChange={(event) => setRuns(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
          />
        </label>
      </div>

      <label className="text-xs text-slate-400">
        Scenario Actions JSON
        <textarea
          value={scenarioInput}
          onChange={(event) => setScenarioInput(event.target.value)}
          rows={12}
          spellCheck={false}
          className="mt-1 w-full rounded-2xl border border-white/10 bg-[#09090f] px-4 py-3 font-mono text-[12px] leading-5 text-slate-200 focus:border-emerald-500/50 focus:outline-none"
        />
      </label>

      <div className="flex gap-2">
        <button
          onClick={runScenario}
          disabled={isRunning || isLoadingSchema}
          className="flex-1 rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-sm font-medium text-emerald-200 transition-colors hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="flex items-center justify-center gap-2">
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run Scenario
          </span>
        </button>
        <button
          onClick={resetScenario}
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <span className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4" />
            Reset
          </span>
        </button>
      </div>

      <div className="rounded-2xl border border-white/5 bg-black/20 p-4">
        <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-widest text-slate-500">
          <FlaskConical className="w-4 h-4 text-emerald-300/80" />
          Result
        </div>
        {!result ? (
          <p className="text-xs text-slate-500">Run a scenario to compare projected queue, pricing, congestion, and active-hub deltas.</p>
        ) : result.status !== 'success' ? (
          <div className="space-y-2 text-xs text-red-200/90">
            <p className="font-medium text-red-300">Scenario rejected</p>
            {(result.validation_errors ?? []).map((error) => (
              <p key={error} className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2">{error}</p>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
              <span className="text-xs text-slate-400">Recommendation</span>
              <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wider ${result.recommendation === 'adopt' ? 'bg-emerald-500/15 text-emerald-200' : result.recommendation === 'caution' ? 'bg-amber-500/15 text-amber-200' : 'bg-red-500/15 text-red-200'}`}>
                {result.recommendation}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(result.delta ?? {}).map(([key, value]) => (
                <div key={key} className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
                  <p className="text-slate-500">{formatActionLabel(key)}</p>
                  <p className={`mt-1 text-sm font-medium ${value > 0 ? 'text-orange-300' : value < 0 ? 'text-emerald-300' : 'text-slate-200'}`}>
                    {value > 0 ? '+' : ''}{value}
                  </p>
                </div>
              ))}
            </div>
            
            {result.baseline?.trajectory && result.scenario?.trajectory && (
              <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-3">
                 <p className="mb-2 text-xs text-slate-400">Projection Trajectories</p>
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="total_queue" color="#60a5fa" label="Total Queue Length" />
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="avg_price" color="#f472b6" label="Avg Price ($/kWh)" />
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="avg_congestion" color="#fbbf24" label="Avg Congestion" />
              </div>
            )}
            
            <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-3 text-xs text-slate-300">
              <p className="mb-2 text-slate-500">Applied Actions</p>
              <div className="space-y-2">
                {(result.applied_actions ?? []).map((action, index) => (
                  <div key={`${String(action.type)}-${index}`} className="rounded-lg border border-white/5 bg-black/20 px-3 py-2 font-mono text-[11px]">
                    {JSON.stringify(action)}
                  </div>
                ))}
              </div>
            </div>
            <p className="text-[11px] text-emerald-200/80">
              Live state mutated: {String(result.safety?.mutates_live_state ?? false)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}