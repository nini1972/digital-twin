'use client';

import { useState } from 'react';
import { Brain, Search, Database, AlertCircle, Clock } from 'lucide-react';

type MemoryResult = {
  text: string;
  metadata: {
    event_type: string;
    timestamp: string;
    [key: string]: string;
  };
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  congestion_hotspot: 'bg-red-500/20 text-red-300 border-red-500/30',
  rebalance_hub_load: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  optimize_hub_pricing: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  status_nominal: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
};

export default function SemanticMemory() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MemoryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/city/memory?q=${encodeURIComponent(searchQuery)}`);
      if (!res.ok) {
        throw new Error(`HTTP Error ${res.status}`);
      }
      const data = await res.json();
      setResults(data.results || []);
    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to search memory');
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    handleSearch(suggestion);
  };

  const formatTimestamp = (isoString?: string) => {
    if (!isoString) return 'Unknown Time';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' - ' + d.toLocaleDateString();
    } catch {
      return isoString;
    }
  };

  return (
    <div className="p-6 rounded-[2rem] border border-white/5 bg-[#12121a]/60 backdrop-blur-2xl shadow-2xl flex flex-col gap-4 relative overflow-hidden group transition-all duration-500 hover:border-orange-500/10">
      {/* Glow Effects */}
      <div className="absolute top-0 right-0 w-[200px] h-[200px] bg-purple-500/5 blur-[80px] rounded-full pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[150px] h-[150px] bg-orange-500/5 blur-[60px] rounded-full pointer-events-none" />

      {/* Header */}
      <div className="flex items-center gap-2.5">
        <Brain className="w-5 h-5 text-purple-400 animate-pulse" />
        <div>
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Semantic Memory Search</h2>
          <p className="text-[10px] text-slate-500 mt-0.5">Recall historical city twin simulation patterns</p>
        </div>
      </div>

      {/* Search Input Box */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
          placeholder="e.g. storm congestion, hub_3 queues..."
          className="w-full bg-black/40 border border-white/10 rounded-xl py-2 px-3.5 pr-10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500/40 focus:ring-1 focus:ring-purple-500/20 transition-all font-light"
        />
        <button
          type="button"
          onClick={() => handleSearch(query)}
          disabled={loading}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors cursor-pointer"
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Search className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Suggestion Chips */}
      <div className="flex flex-wrap gap-1.5">
        {['Grid Stress', 'Hub Saturation', 'Traffic Congestion', 'Dynamic Pricing'].map((chip) => (
          <button
            key={chip}
            type="button"
            onClick={() => handleSuggestionClick(chip)}
            className="text-[9px] font-mono tracking-wider uppercase px-2.5 py-1 rounded-lg border border-white/5 bg-white/[0.01] hover:bg-purple-500/10 hover:text-purple-300 hover:border-purple-500/20 transition-all cursor-pointer text-slate-400"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Results Terminal */}
      <div className="h-64 overflow-y-auto bg-black/45 rounded-2xl p-3 border border-white/5 flex flex-col gap-2.5 scrollbar-thin">
        {loading && (
          <div className="h-full flex flex-col items-center justify-center gap-2 text-slate-500">
            <Database className="w-6 h-6 animate-bounce text-purple-400/50" />
            <p className="text-[10px] font-mono tracking-wider animate-pulse">Retrieving vector embeddings...</p>
          </div>
        )}

        {!loading && error && (
          <div className="h-full flex flex-col items-center justify-center gap-2 text-red-400/80 p-4 text-center">
            <AlertCircle className="w-5 h-5" />
            <p className="text-xs">{error}</p>
          </div>
        )}

        {!loading && !error && results.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center gap-1.5 text-slate-600 text-center p-4">
            <Database className="w-5 h-5 text-slate-700" />
            <p className="text-[10px] font-light">No historical records recalled. Try searching for a pattern above.</p>
          </div>
        )}

        {!loading && !error && results.length > 0 && results.map((res, index) => {
          const type = res.metadata.event_type || 'event';
          const typeClass = EVENT_TYPE_COLORS[type] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
          
          return (
            <div 
              key={index} 
              className="p-3.5 rounded-xl border border-white/5 bg-gradient-to-br from-white/[0.01] to-transparent hover:bg-white/[0.03] transition-all flex flex-col gap-2"
            >
              <div className="flex justify-between items-center">
                <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border uppercase ${typeClass}`}>
                  {type.replace(/_/g, ' ')}
                </span>
                <span className="text-[8px] font-mono text-slate-500 flex items-center gap-1">
                  <Clock className="w-2.5 h-2.5" />
                  {formatTimestamp(res.metadata.timestamp)}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-light font-sans pl-0.5">
                {res.text}
              </p>
              {/* Optional Metadata details */}
              {Object.keys(res.metadata).some(k => k !== 'event_type' && k !== 'timestamp') && (
                <div className="mt-1 flex flex-wrap gap-1.5 pl-0.5">
                  {Object.entries(res.metadata).map(([k, v]) => {
                    if (k === 'event_type' || k === 'timestamp') return null;
                    return (
                      <span key={k} className="text-[8px] font-mono bg-black/60 border border-white/5 px-1.5 py-0.5 rounded text-slate-400">
                        {k}: <span className="text-slate-200">{v}</span>
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
