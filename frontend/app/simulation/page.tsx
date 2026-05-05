"use client";

import { useEffect, useState, useRef } from "react";

type Resident = { id: string; x: number; y: number; battery: number; charging: boolean };
type Hub = { id: string; x: number; y: number; price: number; queue: number };
type SimState = { residents: Resident[]; hubs: Hub[] };

export default function SimulationPage() {
  const [simState, setSimState] = useState<SimState>({ residents: [], hubs: [] });
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to our FastAPI WebSocket
    const ws = new WebSocket("ws://localhost:8000/ws/simulation");
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setSimState(data);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const addHub = () => {
    wsRef.current?.send("add_hub");
  };

  const addResident = () => {
    wsRef.current?.send("add_resident");
  };

  return (
    <div className="min-h-screen bg-[#050508] text-white overflow-hidden flex flex-col font-sans selection:bg-pink-500/30">
      
      {/* Premium Header */}
      <header className="px-8 py-5 flex justify-between items-center border-b border-white/5 bg-black/20 backdrop-blur-xl relative z-20 shadow-lg">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-blue-600 to-pink-500 shadow-[0_0_20px_rgba(236,72,153,0.5)] animate-pulse" />
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent tracking-tight">
              Agentic EV Micro-Twin
            </h1>
            <p className="text-xs text-slate-400 uppercase tracking-widest mt-1">Live Simulation</p>
          </div>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={addResident} 
            className="px-6 py-2.5 rounded-full border border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 text-sm font-medium transition-all shadow-[0_0_15px_rgba(59,130,246,0.15)] hover:shadow-[0_0_25px_rgba(59,130,246,0.3)] hover:-translate-y-0.5"
          >
            + Add Resident Agent
          </button>
          <button 
            onClick={addHub} 
            className="px-6 py-2.5 rounded-full border border-pink-500/30 bg-pink-500/10 hover:bg-pink-500/20 text-pink-300 text-sm font-medium transition-all shadow-[0_0_15px_rgba(236,72,153,0.15)] hover:shadow-[0_0_25px_rgba(236,72,153,0.3)] hover:-translate-y-0.5"
          >
            + Add Charging Hub
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex p-6 gap-6 relative z-10">
        
        {/* The Digital Canvas (City Map) */}
        <div className="flex-1 relative rounded-[2rem] border border-white/5 bg-[#0a0a10]/80 backdrop-blur-3xl overflow-hidden shadow-2xl flex items-center justify-center group">
           
           {/* Dynamic Glowing Background Gradients */}
           <div className="absolute top-0 left-0 w-[500px] h-[500px] bg-blue-600/10 blur-[120px] rounded-full mix-blend-screen pointer-events-none" />
           <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-pink-600/10 blur-[120px] rounded-full mix-blend-screen pointer-events-none" />

           {/* Grid Pattern */}
           <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] opacity-50" />
           
           {/* SVG Map */}
           <svg className="w-full h-full max-w-[800px] max-h-[800px] drop-shadow-2xl relative z-10" viewBox="-10 -10 120 120">
              
              {/* Render Charging Hub Agents */}
              {simState.hubs.map((hub) => (
                <g key={hub.id} className="transition-all duration-[500ms] ease-out" transform={`translate(${hub.x}, ${hub.y})`}>
                  {/* Radar pulse effect */}
                  <circle r="8" className="fill-pink-500/10 stroke-pink-500/30 stroke-[0.2] animate-ping" style={{ animationDuration: '3s' }} />
                  <circle r="5" className="fill-pink-500/20 stroke-pink-500/50 stroke-[0.5]" />
                  <circle r="1.5" className="fill-pink-400 shadow-[0_0_15px_#ec4899]" />
                  
                  {/* Info Tags */}
                  <rect x="-8" y="-12" width="16" height="5" rx="1" fill="#1e1e2d" className="opacity-0 group-hover:opacity-100 transition-opacity" />
                  <text y="-8" className="text-[2.5px] fill-pink-200 font-mono opacity-0 group-hover:opacity-100 transition-opacity" textAnchor="middle">${hub.price.toFixed(2)}</text>
                  
                  <rect x="-8" y="7" width="16" height="5" rx="1" fill="#1e1e2d" />
                  <text y="10.5" className="text-[2.5px] fill-slate-300 font-mono" textAnchor="middle">Q:{hub.queue}</text>
                </g>
              ))}

              {/* Render Resident Agents */}
              {simState.residents.map((res) => {
                // Determine color based on state
                const isCritical = res.battery < 30;
                const baseColor = res.charging ? '#4ade80' : (isCritical ? '#ef4444' : '#60a5fa');
                const glowClass = res.charging ? 'drop-shadow-[0_0_4px_rgba(74,222,128,0.8)]' : '';

                return (
                  <g key={res.id} className={`transition-all duration-[500ms] ease-linear ${glowClass}`} transform={`translate(${res.x}, ${res.y})`}>
                    
                    {/* The Car / Agent */}
                    <circle r={res.charging ? "1.5" : "0.8"} fill={baseColor} />
                    
                    {/* Battery indicator ring */}
                    <g transform="rotate(-90)">
                      <circle r="2.5" fill="none" className="stroke-white/5 stroke-[0.4]" />
                      <circle 
                        r="2.5" 
                        fill="none" 
                        stroke={baseColor}
                        strokeDasharray={`${(res.battery / 100) * (2 * Math.PI * 2.5)} 100`}
                        className="stroke-[0.5] transition-all duration-300" 
                      />
                    </g>

                    {/* Agent ID on hover */}
                    <text y="-4" className="text-[1.5px] fill-white/50 font-mono opacity-0 group-hover:opacity-100 transition-opacity" textAnchor="middle">{res.id}</text>
                  </g>
                );
              })}
           </svg>
        </div>

        {/* Right Sidebar: Real-time Analytics Dashboard */}
        <div className="w-[340px] flex flex-col gap-6">
          
          {/* Top Widget: Metrics */}
          <div className="p-7 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl">
            <h2 className="text-sm font-semibold uppercase tracking-widest mb-6 text-slate-400">City Telemetry</h2>
            
            <div className="flex flex-col gap-5">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">Resident Agents</p>
                <p className="text-3xl font-light text-blue-400 tracking-tighter">{simState.residents.length}</p>
              </div>
              <div className="h-[1px] w-full bg-gradient-to-r from-white/5 to-transparent" />
              
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">Active Hubs</p>
                <p className="text-3xl font-light text-pink-400 tracking-tighter">{simState.hubs.length}</p>
              </div>
              <div className="h-[1px] w-full bg-gradient-to-r from-white/5 to-transparent" />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <p className="text-sm text-slate-400">Charging Now</p>
                </div>
                <p className="text-3xl font-light text-green-400 tracking-tighter">
                  {simState.residents.filter(r => r.charging).length}
                </p>
              </div>
            </div>
          </div>

          {/* Bottom Widget: Live Agent Pricing */}
          <div className="flex-1 p-7 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col">
             <div className="flex justify-between items-center mb-6">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">Live Hub Markets</h2>
                <span className="flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-pink-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-pink-500"></span>
                </span>
             </div>
             
             <div className="space-y-3 overflow-y-auto pr-2 custom-scrollbar flex-1">
               {simState.hubs.map(hub => (
                 <div key={hub.id} className="flex justify-between items-center p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-colors group">
                   <div>
                     <p className="text-sm font-medium text-slate-200">{hub.id.toUpperCase()}</p>
                     <p className="text-xs text-slate-500 mt-0.5">Queue: <span className="text-slate-300 font-mono">{hub.queue} cars</span></p>
                   </div>
                   <div className="text-right">
                     <p className="text-lg text-pink-300 font-mono group-hover:scale-105 transition-transform">${hub.price.toFixed(2)}<span className="text-xs text-pink-500/50">/kWh</span></p>
                   </div>
                 </div>
               ))}
               {simState.hubs.length === 0 && (
                 <div className="h-full flex items-center justify-center text-slate-500 text-sm italic">
                   No active hubs in sector.
                 </div>
               )}
             </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
