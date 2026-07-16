import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface SimulationMetrics {
  avg_price: number;
  wholesale_energy_price_eur_kwh: number;
  profit_margin_eur_kwh: number;
  estimated_hourly_profit_eur: number;
  weather: string;
}

interface WebSocketState {
  metrics: SimulationMetrics;
}

interface MarginHistoryPoint {
  time: string;
  winst_per_uur: number;
  marge: number;
}

export const ProfitMarginWidget: React.FC = () => {
  const [currentMetrics, setCurrentMetrics] = useState<SimulationMetrics | null>(null);
  const [historyData, setHistoryData] = useState<MarginHistoryPoint[]>([]);

  useEffect(() => {
    const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || `ws://${host}:8000/ws/city`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const state: WebSocketState = JSON.parse(event.data);
      if (state.metrics) {
        setCurrentMetrics(state.metrics);
        
        // Voeg toe aan historische array voor de live grafiek (maximaal 20 datapunten)
        setHistoryData((prev) => [
          ...prev,
          {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            winst_per_uur: state.metrics.estimated_hourly_profit_eur,
            marge: state.metrics.profit_margin_eur_kwh * 100 // Weergeven in Eurocents
          }
        ].slice(-20));
      }
    };

    return () => ws.close();
  }, []);

  if (!currentMetrics) return <div className="text-gray-500 animate-pulse">Wachten op live financiële data...</div>;

  return (
    <div className="p-6 bg-slate-900 text-white rounded-xl shadow-lg border border-slate-800">
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-slate-800 p-4 rounded-lg">
          <span className="text-xs text-gray-400 block uppercase font-semibold">Netto Marge per kWh</span>
          <span className="text-2xl font-bold text-green-400">€{currentMetrics.profit_margin_eur_kwh.toFixed(4)}</span>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg">
          <span className="text-xs text-gray-400 block uppercase font-semibold">Geprognotiseerde Winst / Uur</span>
          <span className="text-2xl font-bold text-blue-400">€{currentMetrics.estimated_hourly_profit_eur.toFixed(2)}</span>
        </div>
      </div>

      <h3 className="text-sm font-semibold text-gray-300 mb-3">Live Rendement Trend (€ / Uur)</h3>
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={historyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="time" stroke="#94a3b8" fontSize={10} />
            <YAxis stroke="#94a3b8" fontSize={10} />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }} />
            <Line type="monotone" dataKey="winst_per_uur" stroke="#3b82f6" strokeWidth={3} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
