'use client';

import { useEffect, useMemo, useState } from 'react';
import { 
  FlaskConical, 
  Loader2, 
  Play, 
  RotateCcw, 
  ShieldCheck, 
  Trash2, 
  Plus, 
  Code, 
  LayoutGrid, 
  Sun, 
  CloudRain, 
  Snowflake, 
  Thermometer, 
  Zap, 
  DollarSign, 
  Activity, 
  Users, 
  Compass,
  ArrowRight,
  Sparkles
} from 'lucide-react';

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

  // Editor mode: 'visual' or 'json'
  const [mode, setMode] = useState<'visual' | 'json'>('visual');

  // JSON Mode input state
  const [scenarioInput, setScenarioInput] = useState('');

  // Visual Mode action timeline state
  const [visualActions, setVisualActions] = useState<any[]>(DEFAULT_ACTIONS);

  // Form states for creating a new action
  const [newActionType, setNewActionType] = useState('set_weather');
  const [weatherValue, setWeatherValue] = useState('storm');
  const [zoneValue, setZoneValue] = useState('1,2');
  const [multiplierValue, setMultiplierValue] = useState(0.6);
  const [countValue, setCountValue] = useState(10);
  const [hubIdValue, setHubIdValue] = useState('hub_0');
  const [priceValue, setPriceValue] = useState(0.15);
  const [activeValue, setActiveValue] = useState(true);
  const [strategyValue, setStrategyValue] = useState('hybrid');
  const [aggressivenessValue, setAggressivenessValue] = useState(0.7);
  const [maxActionsValue, setMaxActionsValue] = useState(3);
  const [objectiveValue, setObjectiveValue] = useState('balanced');
  const [floorValue, setFloorValue] = useState(0.10);
  const [ceilingValue, setCeilingValue] = useState(0.50);
  const [maxDeltaValue, setMaxDeltaValue] = useState(0.02);
  const [fairnessWeightValue, setFairnessWeightValue] = useState(0.5);

  const [horizonTicks, setHorizonTicks] = useState(30);
  const [runs, setRuns] = useState(3);
  const [result, setResult] = useState<ScenarioRunResult | null>(null);

  // Load Schema on mount
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

  // Sync mode changes
  const toggleMode = (newMode: 'visual' | 'json') => {
    if (newMode === 'json') {
      // Serialize visual timeline to JSON
      setScenarioInput(JSON.stringify(visualActions, null, 2));
    } else {
      // Parse JSON back to visual timeline
      try {
        const parsed = JSON.parse(scenarioInput);
        const list = Array.isArray(parsed) ? parsed : [parsed];
        setVisualActions(list);
      } catch (err) {
        console.warn("Invalid JSON in textarea, could not sync back to Visual mode", err);
      }
    }
    setMode(newMode);
  };

  const addVisualAction = () => {
    let actionObj: any = { type: newActionType };
    
    switch (newActionType) {
      case 'set_weather':
        actionObj.weather = weatherValue;
        break;
      case 'set_signal_timing':
        actionObj.zone = zoneValue;
        actionObj.multiplier = multiplierValue;
        break;
      case 'add_city_traffic':
        actionObj.count = countValue;
        actionObj.zone = zoneValue;
        break;
      case 'set_hub_price':
        actionObj.hub_id = hubIdValue;
        actionObj.price = priceValue;
        break;
      case 'set_hub_active_state':
        actionObj.hub_id = hubIdValue;
        actionObj.active = activeValue;
        break;
      case 'reroute_traffic':
        actionObj.zone = zoneValue;
        break;
      case 'rebalance_hub_load':
        actionObj.strategy = strategyValue;
        actionObj.max_actions = maxActionsValue;
        actionObj.zone = zoneValue;
        actionObj.aggressiveness = aggressivenessValue;
        break;
      case 'optimize_hub_pricing':
        actionObj.objective = objectiveValue;
        actionObj.floor = floorValue;
        actionObj.ceiling = ceilingValue;
        actionObj.max_delta = maxDeltaValue;
        actionObj.fairness_weight = fairnessWeightValue;
        break;
      case 'add_city_resident':
      case 'add_city_hub':
      case 'trigger_hub_maintenance':
        // No parameters required
        break;
    }

    setVisualActions([...visualActions, actionObj]);
  };

  const removeVisualAction = (indexToRemove: number) => {
    setVisualActions(visualActions.filter((_, idx) => idx !== indexToRemove));
  };

  const resetScenario = () => {
    setVisualActions(DEFAULT_ACTIONS);
    setScenarioInput(JSON.stringify(DEFAULT_ACTIONS, null, 2));
    setResult(null);
  };

  const runScenario = async () => {
    setIsRunning(true);
    setResult(null);

    let scenarioActions: any[] = [];
    if (mode === 'visual') {
      scenarioActions = visualActions;
    } else {
      try {
        const parsed = JSON.parse(scenarioInput);
        scenarioActions = Array.isArray(parsed) ? parsed : [parsed];
      } catch (error) {
        setResult({
          status: 'error',
          validation_errors: [`JSON Parse Error: ${String(error)}`],
        });
        setIsRunning(false);
        return;
      }
    }

    try {
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
    <div className="p-6 rounded-[2rem] border border-emerald-500/10 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-4 relative hover:border-emerald-500/20 transition-all duration-500">
      {/* Glow Effect */}
      <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-emerald-500/5 blur-[80px] rounded-full pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between gap-3 relative z-10">
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-emerald-300/80 flex items-center gap-1.5">
            <FlaskConical className="w-4 h-4 text-emerald-400" /> Scenario Lab
          </h2>
          <p className="mt-0.5 text-[10px] text-slate-500">Copy-only what-if control plane for City Oracle actions.</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] text-emerald-200">
          <ShieldCheck className="w-3 h-3" />
          Safe Sim
        </div>
      </div>

      {/* Mode Switcher */}
      <div className="flex rounded-xl bg-black/40 p-0.5 border border-white/5 relative z-10 self-start">
        <button
          type="button"
          onClick={() => toggleMode('visual')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-all cursor-pointer ${
            mode === 'visual' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 shadow-sm' : 'text-slate-500 hover:text-slate-300 border border-transparent'
          }`}
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          Visual Builder
        </button>
        <button
          type="button"
          onClick={() => toggleMode('json')}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[10px] font-mono tracking-wider uppercase transition-all cursor-pointer ${
            mode === 'json' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 shadow-sm' : 'text-slate-500 hover:text-slate-300 border border-transparent'
          }`}
        >
          <Code className="w-3.5 h-3.5" />
          Raw JSON
        </button>
      </div>

      {/* Editor Content */}
      <div className="relative z-10">
        {mode === 'json' ? (
          <label className="text-[10px] uppercase font-semibold tracking-wider text-slate-500 block mb-1">
            Scenario Actions JSON
            <textarea
              value={scenarioInput}
              onChange={(event) => setScenarioInput(event.target.value)}
              rows={10}
              spellCheck={false}
              className="mt-1 w-full rounded-2xl border border-white/10 bg-[#09090f] p-4 font-mono text-[11px] leading-5 text-slate-200 focus:border-emerald-500/50 focus:outline-none"
            />
          </label>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Action Timeline List */}
            <div className="flex flex-col gap-2">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-slate-500">Action Timeline</span>
              <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
                {visualActions.length === 0 ? (
                  <p className="text-xs text-slate-600 italic py-2 pl-1">No actions in timeline. Add one below.</p>
                ) : (
                  visualActions.map((act, index) => (
                    <div key={index} className="flex justify-between items-center bg-black/40 border border-white/5 rounded-xl p-3 hover:border-white/10 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-6 h-6 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center font-mono text-emerald-400 text-[10px] font-bold">
                          {index + 1}
                        </div>
                        <div>
                          <p className="text-xs text-slate-200 capitalize font-medium">{formatActionLabel(act.type)}</p>
                          <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                            {act.type === 'set_weather' && `weather: ${act.weather}`}
                            {act.type === 'set_signal_timing' && `zone: ${act.zone} | mult: ${act.multiplier}x`}
                            {act.type === 'add_city_traffic' && `count: ${act.count} | zone: ${act.zone || 'random'}`}
                            {act.type === 'set_hub_price' && `hub: ${act.hub_id} | price: $${act.price}`}
                            {act.type === 'set_hub_active_state' && `hub: ${act.hub_id} | active: ${String(act.active)}`}
                            {act.type === 'reroute_traffic' && `zone: ${act.zone}`}
                            {act.type === 'rebalance_hub_load' && `strategy: ${act.strategy} | zone: ${act.zone || 'global'}`}
                            {act.type === 'optimize_hub_pricing' && `objective: ${act.objective}`}
                            {['add_city_resident', 'add_city_hub', 'trigger_hub_maintenance'].includes(act.type) && 'No params'}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeVisualAction(index)}
                        className="p-1.5 rounded-lg border border-white/5 bg-white/[0.01] hover:bg-red-500/10 text-slate-500 hover:text-red-400 hover:border-red-500/20 transition-all cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Add Action Control Panel */}
            <div className="p-4 rounded-2xl border border-white/5 bg-white/[0.01] flex flex-col gap-3.5">
              <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400 flex items-center gap-1.5">
                <Sparkles className="w-3 h-3 text-emerald-400" /> Action Constructor
              </span>

              {/* Action Type Dropdown */}
              <div className="flex flex-col gap-1">
                <span className="text-[9px] text-slate-500 uppercase tracking-wider font-semibold">Select Action Type</span>
                <select
                  value={newActionType}
                  onChange={(e) => setNewActionType(e.target.value)}
                  className="bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-emerald-500/40"
                >
                  <option value="set_weather">Set Weather</option>
                  <option value="set_signal_timing">Set Signal Timing</option>
                  <option value="add_city_traffic">Add Traffic Agents</option>
                  <option value="set_hub_price">Set Hub Price</option>
                  <option value="set_hub_active_state">Set Hub Active State</option>
                  <option value="reroute_traffic">Reroute Traffic</option>
                  <option value="rebalance_hub_load">Rebalance Hub Load</option>
                  <option value="optimize_hub_pricing">Optimize Hub Pricing</option>
                  <option value="add_city_resident">Add Resident EV</option>
                  <option value="add_city_hub">Add Charging Hub</option>
                  <option value="trigger_hub_maintenance">Trigger Hub Maintenance</option>
                </select>
              </div>

              {/* Action Dynamic Parameter Fields */}
              <div className="p-3 bg-black/30 border border-white/5 rounded-xl text-xs flex flex-col gap-3">
                {/* Weather selection */}
                {newActionType === 'set_weather' && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[9px] text-slate-500 uppercase font-semibold">Weather Type</span>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { val: 'sunny', label: 'Sunny', icon: Sun, color: 'text-amber-300 border-amber-500/20' },
                        { val: 'storm', label: 'Storm', icon: CloudRain, color: 'text-blue-300 border-blue-500/20' },
                        { val: 'winter', label: 'Winter', icon: Snowflake, color: 'text-cyan-300 border-cyan-500/20' }
                      ].map((item) => {
                        const Icon = item.icon;
                        const isSelected = weatherValue === item.val;
                        return (
                          <button
                            key={item.val}
                            type="button"
                            onClick={() => setWeatherValue(item.val)}
                            className={`flex items-center justify-center gap-1.5 p-2 rounded-lg border text-[10px] font-mono tracking-wider transition-all cursor-pointer ${
                              isSelected ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' : 'bg-white/[0.01] border-white/5 text-slate-400 hover:bg-white/[0.02]'
                            }`}
                          >
                            <Icon className="w-3.5 h-3.5" />
                            {item.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Signal Timing selection */}
                {newActionType === 'set_signal_timing' && (
                  <div className="flex flex-col gap-2">
                    <div className="grid grid-cols-2 gap-3">
                      <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                        Zone Key
                        <input
                          type="text"
                          value={zoneValue}
                          onChange={(e) => setZoneValue(e.target.value)}
                          className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                        />
                      </label>
                      <div className="flex flex-col gap-1">
                        <span className="text-[9px] text-slate-500 uppercase font-semibold">Speed Multiplier</span>
                        <span className="font-mono text-[10px] text-emerald-300 mt-1.5">{multiplierValue.toFixed(1)}x</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.1"
                      value={multiplierValue}
                      onChange={(e) => setMultiplierValue(parseFloat(e.target.value))}
                      className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
                    />
                  </div>
                )}

                {/* Add Traffic selection */}
                {newActionType === 'add_city_traffic' && (
                  <div className="grid grid-cols-2 gap-3">
                    <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                      Zone Key
                      <input
                        type="text"
                        value={zoneValue}
                        onChange={(e) => setZoneValue(e.target.value)}
                        className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                      Count
                      <input
                        type="number"
                        min="1"
                        max="50"
                        value={countValue}
                        onChange={(e) => setCountValue(parseInt(e.target.value) || 1)}
                        className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                      />
                    </label>
                  </div>
                )}

                {/* Set Hub Price selection */}
                {newActionType === 'set_hub_price' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-[9px] text-slate-500 uppercase font-semibold">Hub ID</span>
                      <select
                        value={hubIdValue}
                        onChange={(e) => setHubIdValue(e.target.value)}
                        className="mt-0.5 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-[10px] text-slate-300 focus:outline-none"
                      >
                        <option value="hub_0">hub_0</option>
                        <option value="hub_1">hub_1</option>
                        <option value="hub_2">hub_2</option>
                        <option value="hub_3">hub_3</option>
                      </select>
                    </div>
                    <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                      Price ($/kWh)
                      <input
                        type="number"
                        step="0.01"
                        value={priceValue}
                        onChange={(e) => setPriceValue(parseFloat(e.target.value) || 0)}
                        className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                      />
                    </label>
                  </div>
                )}

                {/* Set Hub Active State selection */}
                {newActionType === 'set_hub_active_state' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-[9px] text-slate-500 uppercase font-semibold">Hub ID</span>
                      <select
                        value={hubIdValue}
                        onChange={(e) => setHubIdValue(e.target.value)}
                        className="mt-0.5 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-[10px] text-slate-300 focus:outline-none"
                      >
                        <option value="hub_0">hub_0</option>
                        <option value="hub_1">hub_1</option>
                        <option value="hub_2">hub_2</option>
                        <option value="hub_3">hub_3</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[9px] text-slate-500 uppercase font-semibold">Status</span>
                      <button
                        type="button"
                        onClick={() => setActiveValue(!activeValue)}
                        className={`mt-0.5 flex items-center justify-center p-1.5 rounded-lg border text-[10px] font-mono tracking-wider transition-all cursor-pointer ${
                          activeValue ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' : 'bg-red-500/20 border-red-500/30 text-red-300'
                        }`}
                      >
                        {activeValue ? 'ACTIVE' : 'OFFLINE'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Reroute Traffic selection */}
                {newActionType === 'reroute_traffic' && (
                  <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                    Target Congested Zone
                    <input
                      type="text"
                      value={zoneValue}
                      onChange={(e) => setZoneValue(e.target.value)}
                      className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                    />
                  </label>
                )}

                {/* Rebalance Hub Load selection */}
                {newActionType === 'rebalance_hub_load' && (
                  <div className="flex flex-col gap-2">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <span className="text-[9px] text-slate-500 uppercase font-semibold">Strategy</span>
                        <select
                          value={strategyValue}
                          onChange={(e) => setStrategyValue(e.target.value)}
                          className="mt-0.5 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-[10px] text-slate-300 focus:outline-none"
                        >
                          <option value="hybrid">Hybrid</option>
                          <option value="price">Price Only</option>
                          <option value="reroute">Reroute Only</option>
                        </select>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-[9px] text-slate-500 uppercase font-semibold">Aggressiveness</span>
                        <span className="font-mono text-[10px] text-emerald-300 mt-1.5">{aggressivenessValue.toFixed(1)}</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.1"
                      value={aggressivenessValue}
                      onChange={(e) => setAggressivenessValue(parseFloat(e.target.value))}
                      className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-400"
                    />
                  </div>
                )}

                {/* Optimize Hub Pricing selection */}
                {newActionType === 'optimize_hub_pricing' && (
                  <div className="flex flex-col gap-2.5">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <span className="text-[9px] text-slate-500 uppercase font-semibold">Objective</span>
                        <select
                          value={objectiveValue}
                          onChange={(e) => setObjectiveValue(e.target.value)}
                          className="mt-0.5 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-[10px] text-slate-300 focus:outline-none"
                        >
                          <option value="balanced">Balanced</option>
                          <option value="queue_reduction">Queue Reduction</option>
                          <option value="max_throughput">Max Throughput</option>
                          <option value="fairness">Fairness</option>
                        </select>
                      </div>
                      <label className="flex flex-col gap-1 text-[9px] text-slate-500 uppercase font-semibold">
                        Max price change delta
                        <input
                          type="number"
                          step="0.005"
                          min="0.005"
                          max="0.05"
                          value={maxDeltaValue}
                          onChange={(e) => setMaxDeltaValue(parseFloat(e.target.value) || 0.02)}
                          className="mt-0.5 w-full bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 font-mono text-[10px] text-slate-300 focus:outline-none"
                        />
                      </label>
                    </div>
                  </div>
                )}

                {/* Resident EV / Hub / Maintenance parameters info */}
                {['add_city_resident', 'add_city_hub', 'trigger_hub_maintenance'].includes(newActionType) && (
                  <p className="text-[10px] text-slate-500 italic py-1">No target inputs required for this simulation event.</p>
                )}
              </div>

              {/* Add Button */}
              <button
                type="button"
                onClick={addVisualAction}
                className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 text-[10px] font-mono uppercase tracking-wider text-emerald-300 font-bold hover:bg-emerald-500/20 transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Action to Timeline
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Horizon Ticks / Runs Controls */}
      <div className="grid grid-cols-2 gap-3 relative z-10">
        <label className="text-[10px] uppercase font-semibold tracking-wider text-slate-500">
          Horizon Ticks
          <input
            type="number"
            min={schema?.simulate_scenario.horizon_ticks.min ?? 5}
            max={schema?.simulate_scenario.horizon_ticks.max ?? 120}
            value={horizonTicks}
            onChange={(event) => setHorizonTicks(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white focus:border-emerald-500/50 focus:outline-none font-mono"
          />
        </label>
        <label className="text-[10px] uppercase font-semibold tracking-wider text-slate-500">
          Monte Carlo Runs
          <input
            type="number"
            min={schema?.simulate_scenario.runs.min ?? 1}
            max={schema?.simulate_scenario.runs.max ?? 10}
            value={runs}
            onChange={(event) => setRuns(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white focus:border-emerald-500/50 focus:outline-none font-mono"
          />
        </label>
      </div>

      {/* Primary Actions Button Group */}
      <div className="flex gap-2 relative z-10">
        <button
          onClick={runScenario}
          disabled={isRunning || isLoadingSchema}
          className="flex-1 rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-emerald-200 transition-colors hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
        >
          <span className="flex items-center justify-center gap-2">
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run Scenario
          </span>
        </button>
        <button
          onClick={resetScenario}
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-300 transition-colors hover:bg-white/10 cursor-pointer"
        >
          <span className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4" />
            Reset
          </span>
        </button>
      </div>

      {/* Result Panel */}
      <div className="rounded-2xl border border-white/5 bg-black/20 p-4 relative z-10">
        <div className="mb-3 flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500 font-bold">
          <FlaskConical className="w-4 h-4 text-emerald-300/80" />
          Result
        </div>
        {!result ? (
          <p className="text-[10px] text-slate-500 italic">Run a scenario to compare projected queue, pricing, congestion, and active-hub deltas.</p>
        ) : result.status !== 'success' ? (
          <div className="space-y-2 text-xs text-red-200/90 font-sans">
            <p className="font-medium text-red-300">Scenario rejected</p>
            {(result.validation_errors ?? []).map((error) => (
              <p key={error} className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 font-mono text-[10px]">{error}</p>
            ))}
          </div>
        ) : (
          <div className="space-y-3 font-sans">
            <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
              <span className="text-xs text-slate-400">Recommendation</span>
              <span className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-wider ${result.recommendation === 'adopt' ? 'bg-emerald-500/15 text-emerald-200' : result.recommendation === 'caution' ? 'bg-amber-500/15 text-amber-200' : 'bg-red-500/15 text-red-200'}`}>
                {result.recommendation}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {Object.entries(result.delta ?? {}).map(([key, value]) => (
                <div key={key} className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">{formatActionLabel(key)}</p>
                  <p className={`mt-1 text-sm font-medium font-mono ${value > 0 ? 'text-orange-300' : value < 0 ? 'text-emerald-300' : 'text-slate-200'}`}>
                    {value > 0 ? '+' : ''}{value}
                  </p>
                </div>
              ))}
            </div>
            
            {result.baseline?.trajectory && result.scenario?.trajectory && (
              <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-3">
                 <p className="mb-2 text-[10px] uppercase font-bold tracking-wider text-slate-500">Projection Trajectories</p>
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="total_queue" color="#60a5fa" label="Total Queue Length" />
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="avg_price" color="#f472b6" label="Avg Price ($/kWh)" />
                 <TrajectoryChart baseline={result.baseline.trajectory} scenario={result.scenario.trajectory} metric="avg_congestion" color="#fbbf24" label="Avg Congestion" />
              </div>
            )}
            
            <div className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-3 text-xs text-slate-300">
              <p className="mb-2 text-[10px] uppercase font-bold tracking-wider text-slate-500">Applied Actions</p>
              <div className="space-y-1.5 max-h-36 overflow-y-auto scrollbar-thin pr-1">
                {(result.applied_actions ?? []).map((action, index) => (
                  <div key={`${String(action.type)}-${index}`} className="rounded-lg border border-white/5 bg-black/35 px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-slate-300">
                    {JSON.stringify(action)}
                  </div>
                ))}
              </div>
            </div>
            <p className="text-[10px] font-mono text-emerald-200/80 uppercase tracking-wider font-semibold pl-1 flex items-center gap-1.5">
              <ArrowRight className="w-3.5 h-3.5 text-emerald-400" />
              Live state mutated: <span className="text-white">{String(result.safety?.mutates_live_state ?? false)}</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}