'use client';

import React, { useState } from 'react';
import { 
    RefreshCw, 
    AlertTriangle, 
    TrendingUp, 
    CheckCircle2, 
    Calculator, 
    FileText, 
    Database, 
    Terminal, 
    Layers, 
    Check, 
    TrendingDown, 
    PieChart, 
    ShieldAlert, 
    ExternalLink,
    BookOpen,
    Award,
    Send,
    Smartphone,
    Mail,
    Clock,
    Activity
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface FinanceDashboardProps {
    financeState: {
        active_tab: string;
        selected_company: string;
        reports_data: Record<string, any>;
        consolidation_data: Record<string, any>;
        review_data: Record<string, any>;
        data_update_data: Record<string, any>;
        logs: Array<{
            timestamp: string;
            agent: string;
            action: string;
            details: string;
            status: string;
        }>;
        skills?: Array<{
            id: string;
            name: string;
            description: string;
            version: string;
            category: string;
            requires_tools: string[];
            procedure: string;
            filename: string;
        }>;
        midnight_audit_run?: {
            timestamp: string;
            status: string;
            violations_found: number;
            alerts: Array<{
                id: string;
                severity: string;
                title: string;
                message: string;
                reremediation?: string;
                remediation?: string;
            }>;
            integrations: {
                teams: {
                    title: string;
                    adaptive_card: any;
                };
                outlook: {
                    subject: string;
                    html_body: string;
                };
                whatsapp: {
                    message: string;
                };
            };
        } | null;
    };
    activeA2UISurface: any;
    onReset: () => Promise<void>;
    onRefresh: () => Promise<void>;
}

// ============================================================================
// Accounting Utility Formatter
// ============================================================================

const formatCurrency = (val: number | undefined | null, currency: string = "EUR") => {
    const symbol = currency === "USD" ? "$" : "€";
    if (val === undefined || val === null || isNaN(val)) return `${symbol}0.00`;
    
    const formatted = Math.abs(val).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    
    return val < 0 ? `(${symbol}${formatted})` : `${symbol}${formatted}`;
};

const formatPercent = (val: number | undefined | null) => {
    if (val === undefined || val === null || isNaN(val)) return '0.0%';
    const pct = val * 100;
    return `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`;
};

// ============================================================================
// Main Dashboard Component
// ============================================================================

function FinanceDashboard({ 
    financeState, 
    activeA2UISurface, 
    onReset, 
    onRefresh 
}: FinanceDashboardProps) {
    const [activeTab, setActiveTab] = useState<'reports' | 'consolidation' | 'review' | 'logs' | 'skills'>('reports');
    const [selectedCompany, setSelectedCompany] = useState<string>('parent_nv');
    const [selectedPeriod, setSelectedPeriod] = useState<string>('FY25_actual');
    const [isResetting, setIsResetting] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    
    // Skills Hub UI state
    const [expandedSkills, setExpandedSkills] = useState<Record<string, boolean>>({});
    const [activePlatformAlert, setActivePlatformAlert] = useState<'teams' | 'outlook' | 'whatsapp'>('teams');

    const handleRefresh = async () => {
        setIsRefreshing(true);
        await onRefresh();
        setIsRefreshing(false);
    };

    const handleReset = async () => {
        if (confirm("Are you sure you want to reset the financial database and logs back to their baseline?")) {
            setIsResetting(true);
            await onReset();
            setIsResetting(false);
        }
    };

    // Extract records based on selections
    const currentReport = financeState.reports_data[selectedCompany] || null;
    const currentConsolidation = financeState.consolidation_data["group"] || null;
    const currentReview = financeState.review_data["parent_nv"] || null;

    return (
        <div className="flex flex-col h-full bg-slate-950 text-slate-100 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl relative">
            
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl shadow-[0_0_15px_rgba(16,185,129,0.15)]">
                        <Calculator className="w-5 h-5 animate-pulse" />
                    </div>
                    <div>
                        <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
                            Solaria Group Finance Specialist Center
                        </h1>
                        <p className="text-xs text-slate-400">
                            Cortex Multi-Agent Console • BGAAP / IFRS Framework
                        </p>
                    </div>
                </div>

                {/* System Controls */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleRefresh}
                        disabled={isRefreshing}
                        title="Reload latest state"
                        className="p-2 bg-slate-800/80 border border-slate-700/60 text-slate-300 rounded-lg hover:bg-slate-700 hover:text-white disabled:opacity-40 hover:scale-105 active:scale-95 transition-all cursor-pointer"
                    >
                        <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                        onClick={handleReset}
                        disabled={isResetting}
                        className="px-3 py-1.5 bg-rose-500/10 border border-rose-500/25 text-rose-400 text-xs font-semibold rounded-lg hover:bg-rose-500/20 hover:text-rose-300 disabled:opacity-40 transition-all cursor-pointer"
                    >
                        {isResetting ? 'Resetting...' : 'Reset Database'}
                    </button>
                </div>
            </div>

            {/* Sub-Navigation Tabs */}
            <div className="flex items-center justify-between px-5 bg-slate-900/30 border-b border-slate-800/60">
                <div className="flex gap-1 py-2">
                    {[
                        { id: 'reports', label: 'Financial Statements', icon: FileText },
                        { id: 'consolidation', label: 'Consolidation Worksheet', icon: Layers },
                        { id: 'review', label: 'Audits & Analytics', icon: ShieldAlert },
                        { id: 'skills', label: 'Skills Hub', icon: Award },
                        { id: 'logs', label: 'Agent Cortex Logs', icon: Terminal },
                    ].map((tab) => {
                        const Icon = tab.icon;
                        const isAct = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as any)}
                                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                                    isAct 
                                        ? 'bg-slate-800 text-emerald-400 border border-slate-700/50' 
                                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                                }`}
                            >
                                <Icon className="w-3.5 h-3.5" />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>
                <div className="text-[10px] font-mono text-slate-500 select-none">
                    Session: Grounded Live Data
                </div>
            </div>

            {/* Tabs Content Scroll Area */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
                
                {/* MORNING AUDIT ALERT BANNER */}
                {financeState.midnight_audit_run && (
                    <div className="p-4 bg-gradient-to-r from-amber-500/10 via-slate-900/40 to-emerald-500/10 border border-slate-800/80 rounded-xl relative overflow-hidden backdrop-blur-md shadow-lg">
                        <div className="absolute top-0 right-0 w-48 h-48 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />
                        <div className="absolute bottom-0 left-0 w-48 h-48 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />
                        
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div className="flex gap-3 items-start">
                                <div className="p-2 bg-amber-500/15 text-amber-400 border border-amber-500/20 rounded-lg shrink-0 mt-0.5 animate-pulse">
                                    <AlertTriangle className="w-5 h-5" />
                                </div>
                                <div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <h4 className="text-sm font-bold text-slate-200">Overnight Cognitive Audit Report</h4>
                                        <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 text-[9px] font-bold border border-amber-500/15 rounded-full">
                                            {financeState.midnight_audit_run.violations_found} Compliance Warnings
                                        </span>
                                        <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                                            <Clock className="w-3 h-3" />
                                            Ran at {new Date(financeState.midnight_audit_run.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} (Overnight Cron)
                                        </span>
                                    </div>
                                    <p className="text-xs text-slate-400 mt-1.5 leading-relaxed max-w-3xl">
                                        Dominique's Twin ran the multi-agent cognitive ledger audit overnight. Discrepancies were identified in parent_nv research capitalization and flanders_bv intercompany balances. Enterprise alerts were automatically compiled.
                                    </p>
                                    
                                    {/* Action items preview */}
                                    <div className="mt-3 flex gap-2 flex-wrap">
                                        {financeState.midnight_audit_run.alerts.map((alert) => (
                                            <div key={alert.id} className="text-[11px] px-2.5 py-1 bg-slate-900/60 border border-slate-800 rounded-lg text-slate-300 flex items-center gap-1.5">
                                                <span className={`w-1.5 h-1.5 rounded-full ${alert.severity === 'critical' ? 'bg-rose-500' : 'bg-amber-400'}`} />
                                                <span className="font-semibold text-slate-200">{alert.title}:</span>
                                                <span className="text-slate-400 truncate max-w-xs">{alert.message}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                            
                            <div className="flex md:flex-col items-stretch justify-center gap-2 shrink-0">
                                <button
                                    onClick={async () => {
                                        try {
                                            const res = await fetch(`http://localhost:8000/api/finance/trigger-midnight-audit`, { method: 'POST' });
                                            if (res.ok) {
                                                await handleRefresh();
                                                alert("Overnight ledger review re-run executed successfully! Observe the logs in Agent Cortex Logs or Skills Hub tab.");
                                            }
                                        } catch (e) {
                                            console.error(e);
                                        }
                                    }}
                                    className="px-3.5 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/25 hover:border-emerald-500/40 text-emerald-400 text-xs font-semibold rounded-lg transition-all text-center flex items-center gap-1.5 justify-center cursor-pointer hover:scale-[1.02] active:scale-95"
                                >
                                    <Activity className="w-3.5 h-3.5 animate-pulse" />
                                    Trigger Audit Run
                                </button>
                                
                                <button
                                    onClick={() => setActiveTab('skills')}
                                    className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700/50 hover:text-white transition-all text-center flex items-center gap-1.5 justify-center cursor-pointer"
                                >
                                    <Award className="w-3.5 h-3.5" />
                                    View Enterprise Alerts
                                </button>
                            </div>
                        </div>
                    </div>
                )}
                
                {/* 1. REPORTS TAB */}
                {activeTab === 'reports' && (
                    <div className="space-y-6">
                        {/* Interactive Filter Subbar */}
                        <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-900/50 border border-slate-800/80 rounded-xl">
                            <div className="flex items-center gap-4">
                                <div className="flex flex-col gap-1">
                                    <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Focal Entity</label>
                                    <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800">
                                        {[
                                            { id: 'parent_nv', label: 'Parent NV' },
                                            { id: 'flanders_bv', label: 'Flanders BV' },
                                            { id: 'france_sas', label: 'France SAS' },
                                            { id: 'us_inc', label: 'US Inc.' }
                                        ].map((co) => (
                                            <button
                                                key={co.id}
                                                onClick={() => setSelectedCompany(co.id)}
                                                className={`px-2.5 py-1 text-xs font-medium rounded-md cursor-pointer transition-all ${
                                                    selectedCompany === co.id 
                                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                                        : 'text-slate-400 hover:text-slate-200'
                                                }`}
                                            >
                                                {co.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="flex flex-col gap-1">
                                    <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Scenario Period</label>
                                    <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800">
                                        {[
                                            { id: 'FY25_actual', label: 'FY25 Actual' },
                                            { id: 'FY25_budget', label: 'FY25 Budget' }
                                        ].map((per) => (
                                            <button
                                                key={per.id}
                                                onClick={() => setSelectedPeriod(per.id)}
                                                className={`px-2.5 py-1 text-xs font-medium rounded-md cursor-pointer transition-all ${
                                                    selectedPeriod === per.id 
                                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                                        : 'text-slate-400 hover:text-slate-200'
                                                }`}
                                            >
                                                {per.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="text-right">
                                <span className="text-xs text-slate-500">Reporting Currency:</span>
                                <span className="ml-1 text-xs font-semibold text-emerald-400 font-mono bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-500/10">
                                    {selectedCompany === 'us_inc' ? 'USD' : 'EUR'}
                                </span>
                            </div>
                        </div>

                        {currentReport ? (
                            <div className="grid grid-cols-1 gap-6">
                                
                                {/* Income Statement */}
                                {currentReport.income_statement && (
                                    <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                                        <div className="flex items-center gap-2 mb-4">
                                            <FileText className="w-4 h-4 text-emerald-400" />
                                            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                                                Income Statement (P&amp;L) — {currentReport.income_statement.company_name}
                                            </h2>
                                        </div>
                                        <div className="border border-slate-800/60 rounded-lg overflow-hidden">
                                            <table className="w-full text-left border-collapse text-xs font-mono">
                                                <thead>
                                                    <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                        <th className="p-3">Line Account</th>
                                                        <th className="p-3 text-right">Debit / Credit</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850">
                                                        <td className="p-3 pl-5 text-slate-300">Sales Revenues</td>
                                                        <td className="p-3 text-right text-slate-300">{formatCurrency(currentReport.income_statement.rows["Sales"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    {currentReport.income_statement.rows["Intercompany Fee Income"] > 0 && (
                                                        <tr className="hover:bg-slate-850 border-b border-slate-850 text-cyan-400/90 bg-cyan-950/5">
                                                            <td className="p-3 pl-5 font-medium">Intercompany Fee Income</td>
                                                            <td className="p-3 text-right font-semibold">{formatCurrency(currentReport.income_statement.rows["Intercompany Fee Income"], currentReport.income_statement.currency)}</td>
                                                        </tr>
                                                    )}
                                                    <tr className="bg-slate-900/40 border-b border-slate-800/80 text-slate-200 font-semibold">
                                                        <td className="p-3 pl-3">Total Revenues</td>
                                                        <td className="p-3 text-right">{formatCurrency(currentReport.income_statement.rows["Total Revenue"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850 text-rose-300/80">
                                                        <td className="p-3 pl-5">Cost of Goods Sold (COGS)</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["COGS"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="bg-slate-900/10 border-b border-slate-800/80 text-emerald-400 font-bold">
                                                        <td className="p-3 pl-3">Gross Profit</td>
                                                        <td className="p-3 text-right">{formatCurrency(currentReport.income_statement.rows["Gross Profit"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850">
                                                        <td className="p-3 pl-5 text-slate-400">Wages &amp; Salaries</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Wages"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850">
                                                        <td className="p-3 pl-5 text-slate-400">Rent Expense</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Rent"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850">
                                                        <td className="p-3 pl-5 text-slate-400">Depreciation Expense</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Depreciation Expense"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850">
                                                        <td className="p-3 pl-5 text-slate-400">Research &amp; Development Expense</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Research Expense"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    {currentReport.income_statement.rows["Intercompany Fee Expense"] > 0 && (
                                                        <tr className="hover:bg-slate-850 border-b border-slate-850 text-cyan-400/90 bg-cyan-950/5">
                                                            <td className="p-3 pl-5 font-medium">Intercompany Fee Expense</td>
                                                            <td className="p-3 text-right font-semibold">-{formatCurrency(currentReport.income_statement.rows["Intercompany Fee Expense"], currentReport.income_statement.currency)}</td>
                                                        </tr>
                                                    )}
                                                    <tr className="bg-slate-900/40 border-b border-slate-800/80 text-slate-300 font-semibold">
                                                        <td className="p-3 pl-3 text-slate-400">Total Operating Expenses (OPEX)</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Total OPEX"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="bg-slate-900 border-b border-slate-800 text-emerald-400 font-bold">
                                                        <td className="p-3 pl-3">Operating Profit (EBIT)</td>
                                                        <td className="p-3 text-right">{formatCurrency(currentReport.income_statement.rows["Operating Profit (EBIT)"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="hover:bg-slate-850 border-b border-slate-850 text-rose-300/80">
                                                        <td className="p-3 pl-5">Income Tax Expense</td>
                                                        <td className="p-3 text-right">-{formatCurrency(currentReport.income_statement.rows["Income Tax"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                    <tr className="bg-emerald-950/10 text-emerald-300 font-extrabold border-t-2 border-emerald-500/30">
                                                        <td className="p-3 pl-3 text-base">Net Income (Current Year)</td>
                                                        <td className="p-3 text-right text-base">{formatCurrency(currentReport.income_statement.rows["Net Income"], currentReport.income_statement.currency)}</td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}

                                {/* Balance Sheet (Only shown if accounts are valid, not budget) */}
                                {currentReport.balance_sheet && !currentReport.balance_sheet.error ? (
                                    <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-2">
                                                <Database className="w-4 h-4 text-emerald-400" />
                                                <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                                                    Balance Sheet — {currentReport.balance_sheet.company_name}
                                                </h2>
                                            </div>
                                            {currentReport.balance_sheet.is_balanced ? (
                                                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/35 text-emerald-400 text-[10px] font-bold tracking-wide uppercase">
                                                    <Check className="w-3 h-3" /> Balanced
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/35 text-rose-400 text-[10px] font-bold tracking-wide uppercase animate-pulse">
                                                    <AlertTriangle className="w-3 h-3" /> Unbalanced ({formatCurrency(currentReport.balance_sheet.discrepancy, currentReport.balance_sheet.currency)})
                                                </span>
                                            )}
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {/* LEFT column: ASSETS */}
                                            <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-950/20">
                                                <table className="w-full text-left border-collapse text-xs font-mono">
                                                    <thead>
                                                        <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                            <th className="p-3">Asset Ledger Accounts</th>
                                                            <th className="p-3 text-right">Balance</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {Object.entries(currentReport.balance_sheet.assets).map(([key, val]: any) => {
                                                            const isTotal = key === "Total Assets";
                                                            const isCapitalizedResearch = key === "Capitalized Research & Development";
                                                            return (
                                                                <tr 
                                                                    key={key} 
                                                                    className={`hover:bg-slate-850/40 border-b border-slate-850/30 ${
                                                                        isTotal 
                                                                            ? 'bg-slate-900/50 text-emerald-400 font-bold border-t border-slate-800' 
                                                                            : isCapitalizedResearch && val > 0
                                                                                ? 'bg-amber-950/10 text-amber-400'
                                                                                : 'text-slate-300'
                                                                    }`}
                                                                >
                                                                    <td className={`p-3 ${isTotal ? 'pl-3' : 'pl-5'}`}>
                                                                        {key}
                                                                        {isCapitalizedResearch && val > 0 && (
                                                                            <span className="ml-1.5 inline-block px-1.5 py-0.5 text-[8px] font-bold tracking-wider rounded bg-amber-500/10 border border-amber-500/30 uppercase animate-pulse">
                                                                                IAS 38 Audit Violation
                                                                            </span>
                                                                        )}
                                                                    </td>
                                                                    <td className="p-3 text-right">{formatCurrency(val, currentReport.balance_sheet.currency)}</td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* RIGHT column: LIABILITIES & EQUITY */}
                                            <div className="flex flex-col gap-4">
                                                {/* Liabilities */}
                                                <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-950/20">
                                                    <table className="w-full text-left border-collapse text-xs font-mono">
                                                        <thead>
                                                            <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                                <th className="p-3">Liabilities Ledger Accounts</th>
                                                                <th className="p-3 text-right">Balance</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {Object.entries(currentReport.balance_sheet.liabilities).map(([key, val]: any) => {
                                                                const isTotal = key === "Total Liabilities";
                                                                const isIc = key.includes("Intercompany");
                                                                return (
                                                                    <tr 
                                                                        key={key} 
                                                                        className={`hover:bg-slate-850/40 border-b border-slate-850/30 ${
                                                                            isTotal 
                                                                                ? 'bg-slate-900/50 text-slate-200 font-bold border-t border-slate-800' 
                                                                                : isIc
                                                                                    ? 'text-cyan-400/90'
                                                                                    : 'text-slate-300'
                                                                        }`}
                                                                    >
                                                                        <td className={`p-3 ${isTotal ? 'pl-3' : 'pl-5'}`}>{key}</td>
                                                                        <td className="p-3 text-right">{formatCurrency(val, currentReport.balance_sheet.currency)}</td>
                                                                    </tr>
                                                                );
                                                            })}
                                                        </tbody>
                                                    </table>
                                                </div>

                                                {/* Equity */}
                                                <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-950/20">
                                                    <table className="w-full text-left border-collapse text-xs font-mono">
                                                        <thead>
                                                            <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                                <th className="p-3">Shareholders Equity Accounts</th>
                                                                <th className="p-3 text-right">Balance</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {Object.entries(currentReport.balance_sheet.equity).map(([key, val]: any) => {
                                                                const isTotal = key === "Total Equity";
                                                                return (
                                                                    <tr 
                                                                        key={key} 
                                                                        className={`hover:bg-slate-850/40 border-b border-slate-850/30 ${
                                                                            isTotal 
                                                                                ? 'bg-slate-900/50 text-slate-200 font-bold border-t border-slate-800' 
                                                                                : 'text-slate-300'
                                                                        }`}
                                                                    >
                                                                        <td className={`p-3 ${isTotal ? 'pl-3' : 'pl-5'}`}>{key}</td>
                                                                        <td className="p-3 text-right">{formatCurrency(val, currentReport.balance_sheet.currency)}</td>
                                                                    </tr>
                                                                );
                                                            })}
                                                            <tr className="bg-slate-900 text-emerald-400 font-bold">
                                                                <td className="p-3 pl-3">Total Liabilities &amp; Equity</td>
                                                                <td className="p-3 text-right">{formatCurrency(currentReport.balance_sheet.total_liabilities_and_equity, currentReport.balance_sheet.currency)}</td>
                                                            </tr>
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    selectedPeriod === 'FY25_budget' && (
                                        <div className="p-6 text-center border border-slate-800/80 rounded-xl bg-slate-900/10">
                                            <AlertTriangle className="w-8 h-8 text-amber-500/80 mx-auto mb-2" />
                                            <h3 className="text-sm font-semibold text-slate-200">Balance Sheet Unavailable</h3>
                                            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                                                Balance Sheet accounts are only mapped for the "FY25 Actual" ledger period in this financial system. Select "FY25 Actual" to inspect the balance sheet asset ratios.
                                            </p>
                                        </div>
                                    )
                                )}

                                {/* Cash Flow Statement */}
                                {currentReport.cash_flow && !currentReport.cash_flow.error && (
                                    <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                                        <div className="flex items-center gap-2 mb-4">
                                            <TrendingUp className="w-4 h-4 text-emerald-400" />
                                            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                                                Cash Flow Statement — {currentReport.cash_flow.company_name}
                                            </h2>
                                        </div>
                                        <div className="border border-slate-800/60 rounded-lg overflow-hidden">
                                            <table className="w-full text-left border-collapse text-xs font-mono">
                                                <thead>
                                                    <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                        <th className="p-3">Cash Flow Activities</th>
                                                        <th className="p-3 text-right">Net Flow</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {Object.entries(currentReport.cash_flow.rows).map(([key, val]: any) => {
                                                        const isMainCategoryTotal = [
                                                            "Net Cash from Operating Activities",
                                                            "Net Cash used in Investing Activities",
                                                            "Net Cash from Financing Activities",
                                                            "Net Increase/Decrease in Cash",
                                                            "Cash at End of Year"
                                                        ].includes(key);
                                                        
                                                        return (
                                                            <tr 
                                                                key={key} 
                                                                className={`hover:bg-slate-850/40 border-b border-slate-850/30 ${
                                                                    isMainCategoryTotal 
                                                                        ? 'bg-slate-900/40 text-emerald-400 font-bold border-t border-slate-800' 
                                                                        : 'text-slate-300'
                                                                }`}
                                                            >
                                                                <td className={`p-3 ${isMainCategoryTotal ? 'pl-3' : 'pl-5'}`}>{key}</td>
                                                                <td className="p-3 text-right">{formatCurrency(val, currentReport.cash_flow.currency)}</td>
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}

                            </div>
                        ) : (
                            <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/5">
                                <Database className="w-10 h-10 text-slate-600 mx-auto mb-3 animate-pulse" />
                                <h3 className="text-sm font-semibold text-slate-300">Financial Reports Data Missing</h3>
                                <p className="text-xs text-slate-500 mt-2 max-w-sm mx-auto">
                                    The active financial session has no loaded statements. Ask Dominique's twin: <span className="text-emerald-400">"Generate our financial statements for this quarter"</span> to activate the dashboard!
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* 2. CONSOLIDATION TAB */}
                {activeTab === 'consolidation' && (
                    <div className="space-y-6">
                        <div className="p-4 bg-emerald-950/10 border border-emerald-500/20 text-slate-300 rounded-xl flex items-start gap-3">
                            <Layers className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                            <div className="text-xs space-y-1">
                                <h4 className="font-bold text-emerald-400">Consolidated Trial Balance Sheet Protocol</h4>
                                <p>
                                    Aggregates individual company trial balances in EUR. Foreign entities (Solaria US Inc.) translated using balance sheet closing rate (<strong>{financeState.consolidation_data["group"]?.consolidation_matrix?.exchange_rates?.USD_EUR_closing || 0.91}</strong>) and income statement average rate (<strong>{financeState.consolidation_data["group"]?.consolidation_matrix?.exchange_rates?.USD_EUR_average || 0.93}</strong>). Elimination entries represent double-entry eliminations for intercompany receivables, fee income/expense, and equity.
                                </p>
                            </div>
                        </div>

                        {currentConsolidation ? (
                            <div className="space-y-6">
                                {/* Horizontal spreadsheet matrix representation */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg overflow-x-auto">
                                    <div className="flex items-center gap-2 mb-4 shrink-0">
                                        <Calculator className="w-4 h-4 text-emerald-400" />
                                        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                                            Group Consolidation Worksheet (FY25 EUR)
                                        </h2>
                                    </div>

                                    <table className="w-full text-left border-collapse text-xs font-mono min-w-[900px]">
                                        <thead>
                                            <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                <th className="p-3 sticky left-0 bg-slate-950/80">Account Ledger (EUR)</th>
                                                <th className="p-3 text-right border-l border-slate-850">Solaria NV</th>
                                                <th className="p-3 text-right">Flanders BV</th>
                                                <th className="p-3 text-right">France SAS</th>
                                                <th className="p-3 text-right">US Inc. (Translated)</th>
                                                <th className="p-3 text-right border-l border-slate-850 text-cyan-400">Elimination Adj.</th>
                                                <th className="p-3 text-right border-l-2 border-emerald-500/30 text-emerald-400 font-bold bg-emerald-950/5">Consolidated Totals</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {/* We can dynamically rebuild a spreadsheet-style trial balance aggregation row-by-row */}
                                            {[
                                                { key: "Cash", label: "Cash & Equivalents", type: "BS" },
                                                { key: "Accounts Receivable", label: "Accounts Receivable", type: "BS" },
                                                { key: "Intercompany Receivable", label: "Intercompany Receivables", type: "BS" },
                                                { key: "Inventory", label: "Inventories", type: "BS" },
                                                { key: "Equipment", label: "PP&amp;E Equipment", type: "BS" },
                                                { key: "Capitalized Research", label: "Capitalized R&amp;D", type: "BS" },
                                                { key: "Accumulated Depreciation", label: "Accumulated Depreciation", type: "BS" },
                                                { key: "Accounts Payable", label: "Accounts Payable", type: "BS_L" },
                                                { key: "Intercompany Payable", label: "Intercompany Payables", type: "BS_L" },
                                                { key: "Intercompany Loan Payable", label: "Intercompany Loans Payable", type: "BS_L" },
                                                { key: "Share Capital", label: "Share Capital", type: "BS_E" },
                                                { key: "Retained Earnings", label: "Retained Earnings", type: "BS_E" },
                                                { key: "Cumulative Translation Adjustment", label: "CTA (Equity)", type: "BS_E" },
                                                { key: "Sales", label: "Sales Revenues", type: "PL_R" },
                                                { key: "Intercompany Fee Income", label: "Intercompany Fee Income", type: "PL_R" },
                                                { key: "COGS", label: "Cost of Goods Sold (COGS)", type: "PL_E" },
                                                { key: "Wages", label: "Wages &amp; Salaries", type: "PL_E" },
                                                { key: "Rent Expense", label: "Rent Expense", type: "PL_E" },
                                                { key: "Depreciation Expense", label: "Depreciation Expense", type: "PL_E" },
                                                { key: "Research Expense", label: "Research Expense", type: "PL_E" },
                                                { key: "Intercompany Fee Expense", label: "Intercompany Fee Expense", type: "PL_E" },
                                                { key: "Income Tax Expense", label: "Income Tax Expense", type: "PL_E" }
                                            ].map((row) => {
                                                // Extract individual trial balances
                                                const getVal = (cid: string) => {
                                                    const raw = financeState.reports_data[cid]?.income_statement?.rows?.[row.key] 
                                                        || financeState.reports_data[cid]?.balance_sheet?.assets?.[row.key]
                                                        || financeState.reports_data[cid]?.balance_sheet?.liabilities?.[row.key]
                                                        || financeState.reports_data[cid]?.balance_sheet?.equity?.[row.key]
                                                        || 0;
                                                    
                                                    // Standardise sign for display: Credits (Liabilities, Equity, Revenues) are stored negative,
                                                    // but we display them positively or formatted in reporting.
                                                    // Wait! To match the matrix perfectly, let's keep exact raw math.
                                                    return raw;
                                                };

                                                const vParent = getVal("parent_nv");
                                                const vFlanders = getVal("flanders_bv");
                                                const vFrance = getVal("france_sas");
                                                
                                                // US Inc needs conversion if it's original USD report.
                                                // Since we have the group consolidation result, we can extract from it!
                                                // Let's compute US Inc Translated on the fly:
                                                const usdClosing = 0.91;
                                                const usdAverage = 0.93;
                                                const rawUsd = financeState.reports_data["us_inc"]?.income_statement?.rows?.[row.key]
                                                    || financeState.reports_data["us_inc"]?.balance_sheet?.assets?.[row.key]
                                                    || financeState.reports_data["us_inc"]?.balance_sheet?.liabilities?.[row.key]
                                                    || financeState.reports_data["us_inc"]?.balance_sheet?.equity?.[row.key]
                                                    || 0;
                                                const isBs = row.type.startsWith("BS");
                                                const vUs = rawUsd * (isBs ? usdClosing : usdAverage);

                                                // Extract elimination adjustments
                                                const elims = currentConsolidation.consolidation_matrix?.elimination_journal || [];
                                                const matchingElims = elims.filter((e: any) => e.account === row.key);
                                                const adjustment = matchingElims.reduce((sum: number, curr: any) => sum + curr.adjustment, 0);

                                                // Extract consolidated totals
                                                const conBs = currentConsolidation.consolidation_matrix?.balance_sheet || {};
                                                const conPl = currentConsolidation.consolidation_matrix?.income_statement || {};
                                                const consolidatedVal = conBs.assets?.[row.key]
                                                    || conBs.liabilities?.[row.key]
                                                    || conBs.equity?.[row.key]
                                                    || conPl?.[row.key]
                                                    || 0;

                                                const hasValues = vParent !== 0 || vFlanders !== 0 || vFrance !== 0 || vUs !== 0 || adjustment !== 0 || consolidatedVal !== 0;
                                                if (!hasValues) return null;

                                                return (
                                                    <tr key={row.key} className="hover:bg-slate-850/50 border-b border-slate-850 text-slate-300">
                                                        <td className="p-3 font-semibold sticky left-0 bg-slate-950/90 z-10 border-r border-slate-850">{row.key}</td>
                                                        <td className="p-3 text-right text-slate-400">{formatCurrency(vParent)}</td>
                                                        <td className="p-3 text-right text-slate-400">{formatCurrency(vFlanders)}</td>
                                                        <td className="p-3 text-right text-slate-400">{formatCurrency(vFrance)}</td>
                                                        <td className="p-3 text-right text-slate-400">{formatCurrency(vUs, "EUR")}</td>
                                                        <td className={`p-3 text-right font-semibold border-l border-slate-850 ${adjustment !== 0 ? 'text-cyan-400 bg-cyan-950/5' : 'text-slate-500'}`}>
                                                            {adjustment !== 0 ? formatCurrency(adjustment) : '—'}
                                                        </td>
                                                        <td className="p-3 text-right font-bold border-l-2 border-emerald-500/30 text-emerald-300 bg-emerald-950/5">
                                                            {formatCurrency(consolidatedVal)}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>

                                {/* Elimination Journal Log */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Layers className="w-4 h-4 text-cyan-400" />
                                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                                            Consolidation Elimination Journal Records
                                        </h3>
                                    </div>
                                    <div className="space-y-3">
                                        {(currentConsolidation.consolidation_matrix?.elimination_journal || []).map((journal: any, idx: number) => (
                                            <div 
                                                key={idx}
                                                className="p-3.5 bg-slate-950/40 border border-slate-800/80 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                                            >
                                                <div className="space-y-1">
                                                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold tracking-wider uppercase bg-cyan-950/50 border border-cyan-500/30 text-cyan-400`}>
                                                        Journal Entry #{idx + 1}
                                                    </span>
                                                    <h4 className="font-semibold text-slate-200 font-mono mt-1">
                                                        {journal.account}
                                                    </h4>
                                                    <p className="text-slate-400">{journal.description}</p>
                                                </div>
                                                <div className="text-right flex flex-row md:flex-col gap-2 md:gap-0 items-center md:items-end justify-between md:justify-center">
                                                    <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold font-mono">{journal.type}</span>
                                                    <span className={`text-base font-bold font-mono ${journal.adjustment > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                        {journal.adjustment > 0 ? 'DEBIT' : 'CREDIT'} • {formatCurrency(Math.abs(journal.adjustment))}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/5">
                                <Layers className="w-10 h-10 text-slate-600 mx-auto mb-3 animate-pulse" />
                                <h3 className="text-sm font-semibold text-slate-300">Group Consolidation Data Missing</h3>
                                <p className="text-xs text-slate-500 mt-2 max-w-sm mx-auto">
                                    Consolidated records have not been compiled yet. Prompt the AI Financial Specialist in chat: <span className="text-emerald-400">"Consolidate our company books and show me the journal entries"</span> to activate the worksheet.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* 3. AUDITS & ANALYTICS TAB */}
                {activeTab === 'review' && (
                    <div className="space-y-6">
                        {currentReview ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                
                                {/* Compliance Alerts Panel */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg space-y-4">
                                    <div className="flex items-center gap-2">
                                        <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />
                                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                                            Accounting Standards Audit Warning (IAS 38)
                                        </h3>
                                    </div>
                                    
                                    {(currentReview.review?.compliance || []).length > 0 ? (
                                        (currentReview.review.compliance).map((issue: any) => (
                                            <div key={issue.issue_id} className="p-4 bg-rose-500/5 border border-rose-500/20 rounded-xl space-y-3 text-xs">
                                                <div className="flex items-center justify-between">
                                                    <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 font-bold text-[10px] tracking-wide border border-rose-500/30 font-mono">
                                                        {issue.standard_violated} VIOLATION
                                                    </span>
                                                    <span className="font-mono text-rose-400 font-extrabold text-sm">
                                                        {formatCurrency(issue.current_value)}
                                                    </span>
                                                </div>
                                                <h4 className="font-bold text-slate-200">{issue.subject}</h4>
                                                <p className="text-slate-400 leading-relaxed">{issue.description}</p>
                                                <div className="pt-2 border-t border-slate-800/60">
                                                    <span className="font-bold text-slate-300">Auditor Action / Remediation:</span>
                                                    <p className="text-emerald-400 font-medium mt-1 bg-emerald-950/10 p-2.5 rounded border border-emerald-500/10">
                                                        {issue.remediation}
                                                    </p>
                                                </div>
                                                <div className="bg-slate-950/60 p-3 rounded border border-slate-800 font-mono text-[10px] text-slate-300 space-y-1">
                                                    <p className="font-bold text-slate-400 uppercase tracking-wider text-[8px] mb-1.5 border-b border-slate-800 pb-1">Recommended Adjusting Journal Entry</p>
                                                    <div className="flex justify-between">
                                                        <span>Dr. {issue.adjusting_entry.Debit}</span>
                                                        <span className="text-emerald-400">{formatCurrency(issue.adjusting_entry.Amount)}</span>
                                                    </div>
                                                    <div className="flex justify-between pl-4 text-slate-400">
                                                        <span>Cr. {issue.adjusting_entry.Credit}</span>
                                                        <span>{formatCurrency(issue.adjusting_entry.Amount)}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="p-6 text-center border border-slate-800 rounded-lg bg-slate-950/10">
                                            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                                            <h4 className="font-bold text-slate-200">No Policy Violations Found</h4>
                                            <p className="text-xs text-slate-500 mt-1">
                                                All accounts fully adhere to IFRS and local Belgian GAAP rules.
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {/* Financial Ratios and Ratios Gauges */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg space-y-4">
                                    <div className="flex items-center gap-2">
                                        <PieChart className="w-4 h-4 text-emerald-400" />
                                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                                            Financial Health &amp; Solvency Ratios
                                        </h3>
                                    </div>

                                    {currentReview.review?.ratios?.metrics ? (
                                        <div className="space-y-4 text-xs font-mono">
                                            {[
                                                { 
                                                    key: "Current Ratio (Liquidity)", 
                                                    desc: "Ability to pay short-term obligations (Current Assets / Current Liab). Target: &gt; 1.5", 
                                                    value: currentReview.review.ratios.metrics["Current Ratio (Liquidity)"], 
                                                    status: currentReview.review.ratios.health_checks["Liquidity Health"],
                                                    color: currentReview.review.ratios.health_checks["Liquidity Health"] === "Healthy" ? "emerald" : "amber",
                                                    max: 3.0
                                                },
                                                { 
                                                    key: "Debt-to-Equity (Solvency)", 
                                                    desc: "Financial leverage of the firm (Total Liabilities / Total Equity). Target: &lt; 1.5", 
                                                    value: currentReview.review.ratios.metrics["Debt-to-Equity (Solvency)"], 
                                                    status: currentReview.review.ratios.health_checks["Leverage Risk"],
                                                    color: currentReview.review.ratios.health_checks["Leverage Risk"].includes("Healthy") ? "emerald" : "amber",
                                                    max: 3.0
                                                }
                                            ].map((ratio) => {
                                                const isHealthy = ratio.color === "emerald";
                                                const pct = Math.min((ratio.value / ratio.max) * 100, 100);
                                                return (
                                                    <div key={ratio.key} className="p-3.5 bg-slate-950/40 border border-slate-800/80 rounded-lg space-y-2">
                                                        <div className="flex justify-between items-center">
                                                            <div>
                                                                <h4 className="font-bold text-slate-200">{ratio.key}</h4>
                                                                <p className="text-[10px] text-slate-500 font-sans mt-0.5">{ratio.desc}</p>
                                                            </div>
                                                            <div className="text-right">
                                                                <span className="text-lg font-bold text-slate-200">{ratio.value}</span>
                                                                <span className={`ml-2 px-2 py-0.5 rounded text-[8px] font-sans font-bold uppercase tracking-wider ${
                                                                    isHealthy 
                                                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25' 
                                                                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/25'
                                                                }`}>
                                                                    {ratio.status}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        {/* Progress bar visual */}
                                                        <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                                                            <div 
                                                                className={`h-full rounded-full transition-all duration-500 ${
                                                                    isHealthy ? 'bg-emerald-500' : 'bg-amber-500'
                                                                }`}
                                                                style={{ width: `${pct}%` }}
                                                            />
                                                        </div>
                                                    </div>
                                                );
                                            })}

                                            <div className="p-3.5 bg-slate-950/40 border border-slate-800/80 rounded-lg flex items-center justify-between">
                                                <div>
                                                    <span className="text-[10px] text-slate-500 font-sans font-semibold uppercase">Net Profit Margin</span>
                                                    <p className="text-sm font-extrabold text-slate-200 mt-0.5">
                                                        {formatPercent(currentReview.review.ratios.metrics["Net Profit Margin"])}
                                                    </p>
                                                </div>
                                                <div className="text-right">
                                                    <span className="text-[10px] text-slate-500 font-sans font-semibold uppercase">Return on Assets (ROA)</span>
                                                    <p className="text-sm font-extrabold text-slate-200 mt-0.5">
                                                        {formatPercent(currentReview.review.ratios.metrics["Return on Assets (ROA)"])}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-500 text-xs">Insufficient data to compile health ratios.</p>
                                    )}
                                </div>

                                {/* Actual vs Budget & YoY Variance Panel */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg md:col-span-2 space-y-4">
                                    <div className="flex items-center gap-2">
                                        <TrendingUp className="w-4 h-4 text-cyan-400" />
                                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                                            Parent Company Variance Analysis (FY25 Solaria NV)
                                        </h3>
                                    </div>

                                    {currentReview.review?.variances?.actual_vs_budget ? (
                                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs font-mono">
                                            {/* Actual vs Budget table */}
                                            <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-950/20">
                                                <div className="bg-slate-900 p-2.5 border-b border-slate-800 text-[10px] font-sans font-bold text-slate-400 uppercase tracking-wider">
                                                    Actual vs Budget Comparison
                                                </div>
                                                <table className="w-full text-left border-collapse">
                                                    <thead>
                                                        <tr className="bg-slate-900/50 border-b border-slate-850 text-slate-500 text-[10px]">
                                                            <th className="p-2.5">Ledger</th>
                                                            <th className="p-2.5 text-right">Actual FY25</th>
                                                            <th className="p-2.5 text-right">Budget FY25</th>
                                                            <th className="p-2.5 text-right">Variance (%)</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {Object.entries(currentReview.review.variances.actual_vs_budget).map(([key, details]: any) => {
                                                            const isFav = key === "Sales" ? details.variance >= 0 : details.variance <= 0;
                                                            return (
                                                                <tr key={key} className="hover:bg-slate-850/40 border-b border-slate-850/30 text-slate-300">
                                                                    <td className="p-2.5 font-semibold text-slate-400">{key}</td>
                                                                    <td className="p-2.5 text-right">{formatCurrency(details.actual)}</td>
                                                                    <td className="p-2.5 text-right">{formatCurrency(details.budget)}</td>
                                                                    <td className={`p-2.5 text-right font-bold ${isFav ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                                        {formatCurrency(details.variance)} ({formatPercent(details.variance_pct)})
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* YoY comparison */}
                                            <div className="border border-slate-800/60 rounded-lg overflow-hidden bg-slate-950/20">
                                                <div className="bg-slate-900 p-2.5 border-b border-slate-800 text-[10px] font-sans font-bold text-slate-400 uppercase tracking-wider">
                                                    Year-over-Year (YoY) Growth Metrics
                                                </div>
                                                <table className="w-full text-left border-collapse">
                                                    <thead>
                                                        <tr className="bg-slate-900/50 border-b border-slate-850 text-slate-500 text-[10px]">
                                                            <th className="p-2.5">Ledger</th>
                                                            <th className="p-2.5 text-right">Current FY25</th>
                                                            <th className="p-2.5 text-right">Prior FY24</th>
                                                            <th className="p-2.5 text-right">YoY Variance (%)</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {Object.entries(currentReview.review.variances.year_over_year).map(([key, details]: any) => {
                                                            const isFav = key === "Sales" ? details.variance >= 0 : details.variance <= 0;
                                                            return (
                                                                <tr key={key} className="hover:bg-slate-850/40 border-b border-slate-850/30 text-slate-300">
                                                                    <td className="p-2.5 font-semibold text-slate-400">{key}</td>
                                                                    <td className="p-2.5 text-right">{formatCurrency(details.current)}</td>
                                                                    <td className="p-2.5 text-right">{formatCurrency(details.prior)}</td>
                                                                    <td className={`p-2.5 text-right font-bold ${isFav ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                                        {formatCurrency(details.variance)} ({formatPercent(details.variance_pct)})
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-500 text-xs">Insufficient data for variance comparisons.</p>
                                    )}

                                    {/* Commentary */}
                                    {currentReview.review?.variances?.audit_commentary && (
                                        <div className="p-4 bg-slate-950/50 border border-slate-800/80 rounded-xl space-y-2 text-xs">
                                            <h4 className="font-bold text-slate-300 font-sans">AI CFO Commentary &amp; Financial Findings:</h4>
                                            <ul className="list-disc pl-4 space-y-1.5 text-slate-400 font-sans">
                                                {(currentReview.review.variances.audit_commentary).map((note: string, index: number) => (
                                                    <li key={index} className="leading-relaxed">{note}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>

                                {/* Intercompany Reconciliation Report */}
                                <div className="bg-slate-900/30 border border-slate-800/80 rounded-xl p-5 shadow-lg md:col-span-2 space-y-4">
                                    <div className="flex items-center gap-2">
                                        <Layers className="w-4 h-4 text-cyan-400" />
                                        <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                                            Intercompany Reconciliation Discrepancy Scans
                                        </h3>
                                    </div>

                                    {currentReview.review?.intercompany?.mismatches ? (
                                        <div className="space-y-3">
                                            {(currentReview.review.intercompany.mismatches).map((mismatch: any) => (
                                                <div 
                                                    key={mismatch.id}
                                                    className="p-4 bg-amber-500/5 border border-amber-500/20 rounded-xl flex items-start gap-3 text-xs"
                                                >
                                                    <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5 animate-pulse" />
                                                    <div className="space-y-1">
                                                        <div className="flex items-center gap-2">
                                                            <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono uppercase">
                                                                LEDGER DISCREPANCY
                                                            </span>
                                                            <span className="font-bold text-slate-200 font-mono">
                                                                {mismatch.from_company_id.toUpperCase()} ⟷ {mismatch.to_company_id.toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <p className="text-slate-300 leading-relaxed font-sans">{mismatch.description}</p>
                                                    </div>
                                                </div>
                                            ))}
                                            <div className="p-3 bg-emerald-500/5 border border-emerald-500/15 rounded-lg flex items-center justify-between text-xs text-slate-400 font-sans">
                                                <span>Total matching intercompany accounts checked:</span>
                                                <span className="font-bold text-emerald-400 font-mono">
                                                    {currentReview.review.intercompany.reconciled_count} entries verified perfectly
                                                </span>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-slate-500 text-xs">No active intercompany check data available.</p>
                                    )}
                                </div>

                            </div>
                        ) : (
                            <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/5">
                                <ShieldAlert className="w-10 h-10 text-slate-600 mx-auto mb-3 animate-pulse" />
                                <h3 className="text-sm font-semibold text-slate-300">Audits &amp; Analytics Data Missing</h3>
                                <p className="text-xs text-slate-500 mt-2 max-w-sm mx-auto">
                                    Auditing checks have not been performed yet. Prompt Dominique's twin: <span className="text-emerald-400">"Run a compliance and audit scan of the group"</span> to inspect ledger violations, solvency ratios, and commentary.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* 4. AGENT LOGS TAB */}
                {activeTab === 'logs' && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                                <Terminal className="w-4 h-4 text-emerald-400" />
                                Multi-Agent Communication Trace Logs
                            </h3>
                            <span className="text-[10px] font-mono text-slate-500">
                                {financeState.logs?.length || 0} processes recorded
                            </span>
                        </div>

                        {financeState.logs && financeState.logs.length > 0 ? (
                            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl font-mono text-xs space-y-4 max-h-[450px] overflow-y-auto shadow-inner">
                                {financeState.logs.map((log, idx) => {
                                    const isFail = log.status === "failed";
                                    let agentColor = "text-emerald-400 border-emerald-500/20 bg-emerald-950/20";
                                    if (log.agent === "Scout") agentColor = "text-amber-400 border-amber-500/20 bg-amber-950/20";
                                    else if (log.agent === "Consolidator") agentColor = "text-blue-400 border-blue-500/20 bg-blue-950/20";
                                    else if (log.agent === "Auditor") agentColor = "text-purple-400 border-purple-500/20 bg-purple-950/20";

                                    return (
                                        <div key={idx} className="border-b border-slate-900 pb-3 last:border-0 last:pb-0 space-y-1">
                                            <div className="flex items-center justify-between text-[10px] text-slate-500">
                                                <div className="flex items-center gap-2">
                                                    <span className={`px-2 py-0.5 border rounded text-[9px] font-bold ${agentColor}`}>
                                                        {log.agent}
                                                    </span>
                                                    <span className="font-bold text-slate-300">
                                                        {log.action}
                                                    </span>
                                                </div>
                                                <span>
                                                    {new Date(log.timestamp).toLocaleTimeString()}
                                                </span>
                                            </div>
                                            <p className={`text-slate-450 leading-relaxed font-sans ${isFail ? 'text-rose-400' : 'text-slate-400'}`}>
                                                {log.details}
                                            </p>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="p-12 text-center border border-slate-800/80 rounded-xl bg-slate-900/10">
                                <Terminal className="w-8 h-8 text-slate-600 mx-auto mb-2 animate-pulse" />
                                <h4 className="font-bold text-slate-300">Cortex Log Database Empty</h4>
                                <p className="text-xs text-slate-500 mt-1">
                                    Interact with Dominique's AI twin in chat to trigger ledger tasks and record the execution logs!
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {/* 5. SKILLS HUB TAB */}
                {activeTab === 'skills' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn text-slate-300">
                        {/* Left/Main Column - Skills Playbook Directory */}
                        <div className="lg:col-span-2 space-y-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                                        <BookOpen className="w-4 h-4 text-emerald-400" />
                                        Procedural Playbook Memory (Tier 3)
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-1">
                                        AI-compiled step-by-step auditing, compliance and consolidation checklists stored in <code className="text-slate-400 font-mono">backend/finance/skills/</code>.
                                    </p>
                                </div>
                                <span className="px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 font-mono text-[10px]">
                                    {financeState.skills?.length || 0} Playbooks Active
                                </span>
                            </div>

                            <div className="space-y-4">
                                {financeState.skills && financeState.skills.length > 0 ? (
                                    financeState.skills.map((skill) => {
                                        const isExpanded = !!expandedSkills[skill.id];
                                        return (
                                            <div key={skill.id} className="bg-slate-900/40 border border-slate-800/80 rounded-xl overflow-hidden backdrop-blur-md transition-all duration-300 hover:border-slate-700/60 shadow-md">
                                                <div className="p-4 flex items-start justify-between gap-4">
                                                    <div className="flex gap-3">
                                                        <div className="p-2.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/15 rounded-xl shrink-0 mt-0.5">
                                                            <Award className="w-5 h-5" />
                                                        </div>
                                                        <div>
                                                            <div className="flex items-center gap-2 flex-wrap">
                                                                <h4 className="text-sm font-bold text-slate-200 font-mono">{skill.name}</h4>
                                                                <span className="px-2 py-0.5 bg-slate-950 text-slate-400 text-[9px] border border-slate-800 rounded-full font-sans uppercase">
                                                                    {skill.category || 'compliance-audit'}
                                                                </span>
                                                            </div>
                                                            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                                                                {skill.description}
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <button
                                                        onClick={() => setExpandedSkills(prev => ({ ...prev, [skill.id]: !isExpanded }))}
                                                        className="px-2.5 py-1.5 bg-slate-850 hover:bg-slate-800 text-slate-300 text-[11px] font-semibold rounded-lg border border-slate-850 transition-all cursor-pointer select-none"
                                                    >
                                                        {isExpanded ? 'Hide Steps' : 'View Steps'}
                                                    </button>
                                                </div>

                                                {isExpanded && (
                                                    <div className="border-t border-slate-800/60 bg-slate-950/40 p-4 space-y-4 animate-slideDown">
                                                        <div className="flex flex-wrap gap-4 text-[11px]">
                                                            <div className="flex items-center gap-1.5 text-slate-400">
                                                                <span className="text-slate-500 font-sans">Tools Required:</span>
                                                                <div className="flex gap-1">
                                                                    {(skill.requires_tools || []).map((t, idx) => (
                                                                        <span key={idx} className="px-2 py-0.5 bg-slate-900 border border-slate-800 text-slate-300 rounded font-mono">
                                                                            {t}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                            <div className="flex items-center gap-1.5 text-slate-400">
                                                                <span className="text-slate-500">File Path:</span>
                                                                <span className="font-mono text-slate-400 text-slate-300">backend/finance/skills/{skill.id}.md</span>
                                                            </div>
                                                        </div>

                                                        <div className="space-y-2">
                                                            <h5 className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">Playbook Procedure</h5>
                                                            <div className="bg-slate-950 p-3 rounded-lg border border-slate-900 font-mono text-xs text-slate-300 space-y-2 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                                                                {skill.procedure}
                                                            </div>
                                                        </div>

                                                        <div className="flex justify-end pt-2">
                                                            <button
                                                                onClick={async () => {
                                                                    try {
                                                                        const res = await fetch(`http://localhost:8000/api/finance/trigger-midnight-audit`, { method: 'POST' });
                                                                        if (res.ok) {
                                                                            await handleRefresh();
                                                                            alert(`Successfully executed check based on playbook ${skill.name}! Real-time trace logged.`);
                                                                        }
                                                                    } catch (err) {
                                                                        console.error(err);
                                                                    }
                                                                }}
                                                                className="px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/25 hover:border-emerald-500/40 text-emerald-400 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
                                                            >
                                                                <Activity className="w-3.5 h-3.5" />
                                                                Execute Verification Run
                                                            </button>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="p-12 text-center border border-dashed border-slate-800 rounded-xl bg-slate-900/5">
                                        <Award className="w-10 h-10 text-slate-600 mx-auto mb-3 animate-pulse" />
                                        <h3 className="text-sm font-semibold text-slate-300">No Procedural Playbooks</h3>
                                        <p className="text-xs text-slate-500 mt-2 max-w-sm mx-auto">
                                            No pre-compiled playbooks are registered. Tell Dominique's twin: <span className="text-emerald-400">"Create a playbook reconcile_ledgers to balance parent and Flanders"</span> to compile one dynamically!
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Right Column - Cortex Logs & Enterprise Alerts */}
                        <div className="space-y-6">
                            {/* Real-time Typewriter Cortex Logs Panel */}
                            <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-4 space-y-3 backdrop-blur-md shadow-md">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                                        <Terminal className="w-4 h-4 text-emerald-400 animate-pulse" />
                                        Cortex Logs
                                    </h4>
                                    <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                                </div>
                                
                                <div className="p-3 bg-slate-950 border border-slate-900 rounded-lg font-mono text-[11px] space-y-3 max-h-[180px] overflow-y-auto leading-relaxed text-slate-400 scrollbar-thin">
                                    {financeState.logs && financeState.logs.length > 0 ? (
                                        financeState.logs.slice(-6).map((log, idx) => (
                                            <div key={idx} className="border-b border-slate-900 pb-2 last:border-0 last:pb-0 space-y-0.5">
                                                <div className="flex items-center justify-between text-[9px] text-slate-500">
                                                    <span className="font-bold text-slate-300">{log.agent} › {log.action}</span>
                                                    <span>{new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
                                                </div>
                                                <p className="text-slate-400 leading-normal line-clamp-2">{log.details}</p>
                                            </div>
                                        ))
                                    ) : (
                                        <p className="text-slate-600 text-center py-4">No cognitive cortex logs yet.</p>
                                    )}
                                </div>
                            </div>

                            {/* Enterprise Integrations Mockup Panel */}
                            {financeState.midnight_audit_run && (
                                <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-4 space-y-4 backdrop-blur-md shadow-md">
                                    <div>
                                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                                            <Send className="w-4 h-4 text-sky-400" />
                                            Enterprise Broadcast Preview
                                        </h4>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            Simulated adaptive briefing packages pushed automatically to enterprise systems.
                                        </p>
                                    </div>

                                    {/* Platform Selector Tabs */}
                                    <div className="flex border border-slate-800 bg-slate-950 p-1 rounded-lg gap-1">
                                        <button
                                            onClick={() => setActivePlatformAlert('teams')}
                                            className={`flex-1 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 justify-center cursor-pointer ${
                                                activePlatformAlert === 'teams'
                                                    ? 'bg-purple-650 text-white shadow-sm'
                                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                                            }`}
                                        >
                                            Teams
                                        </button>
                                        <button
                                            onClick={() => setActivePlatformAlert('outlook')}
                                            className={`flex-1 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 justify-center cursor-pointer ${
                                                activePlatformAlert === 'outlook'
                                                    ? 'bg-blue-600 text-white shadow-sm'
                                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                                            }`}
                                        >
                                            Outlook
                                        </button>
                                        <button
                                            onClick={() => setActivePlatformAlert('whatsapp')}
                                            className={`flex-1 py-1.5 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 justify-center cursor-pointer ${
                                                activePlatformAlert === 'whatsapp'
                                                    ? 'bg-emerald-600 text-white shadow-sm'
                                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                                            }`}
                                        >
                                            WhatsApp
                                        </button>
                                    </div>

                                    {/* High-Fidelity Previews */}
                                    <div className="border border-slate-800 bg-slate-950 rounded-xl overflow-hidden shadow-inner min-h-[220px] flex flex-col">
                                        
                                        {/* TEAMS CARD MOCKUP */}
                                        {activePlatformAlert === 'teams' && (
                                            <div className="p-4 space-y-3 flex-1 bg-white text-slate-800 font-sans text-xs">
                                                <div className="flex items-center gap-2 border-b border-slate-100 pb-2.5">
                                                    <div className="w-6 h-6 rounded-full bg-purple-600 flex items-center justify-center text-[10px] text-white font-bold">
                                                        MS
                                                    </div>
                                                    <div>
                                                        <h5 className="font-bold text-slate-800 leading-tight">Microsoft Teams</h5>
                                                        <p className="text-[10px] text-slate-400">Incoming webhook • Just now</p>
                                                    </div>
                                                </div>
                                                <div className="border-l-4 border-rose-500 pl-3 py-0.5 space-y-2 bg-slate-50/50 p-2.5 rounded-r-lg">
                                                    <h6 className="font-black text-slate-900 text-xs">
                                                        {financeState.midnight_audit_run.integrations.teams.title}
                                                    </h6>
                                                    <p className="text-[11px] text-slate-500">
                                                        Dominique's ledger audit has run and found critical warnings.
                                                    </p>
                                                    
                                                    <div className="grid grid-cols-3 gap-1 py-1.5 border-t border-b border-slate-100 text-[10px]">
                                                        <div className="text-slate-400">Audit Date</div>
                                                        <div className="col-span-2 text-slate-700 font-bold">{new Date(financeState.midnight_audit_run.timestamp).toLocaleDateString()}</div>
                                                        <div className="text-slate-400">Audited Entities</div>
                                                        <div className="col-span-2 text-slate-700 font-bold">parent_nv, flanders_bv</div>
                                                        <div className="text-slate-400">Compliance Status</div>
                                                        <div className="col-span-2 text-rose-650 font-bold">🚨 {financeState.midnight_audit_run.violations_found} Violations Found</div>
                                                    </div>

                                                    <p className="text-[10px] leading-relaxed text-slate-600 bg-rose-50/50 p-2 rounded border border-rose-100">
                                                        <strong>IFRS IAS 38</strong>: Expensing parent_nv Research (EUR 45k) required.<br/>
                                                        <strong>Intercompany</strong>: Flanders BV recorded payable has a EUR 2k mismatch.
                                                    </p>

                                                    <button className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white font-semibold text-[10px] rounded border border-purple-700 transition-all shadow-sm select-none cursor-not-allowed">
                                                        Open Dashboard Console
                                                    </button>
                                                </div>
                                            </div>
                                        )}

                                        {/* OUTLOOK EMAIL MOCKUP */}
                                        {activePlatformAlert === 'outlook' && (
                                            <div className="flex-1 flex flex-col bg-slate-100 text-slate-700 font-sans text-xs">
                                                <div className="bg-slate-200 p-2.5 border-b border-slate-300 flex items-center justify-between text-[10px] text-slate-500 font-medium">
                                                    <div className="flex items-center gap-1.5">
                                                        <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                                                        Outlook Mail Client
                                                    </div>
                                                    <span>In-Box Preview</span>
                                                </div>
                                                <div className="p-3 bg-white border-b border-slate-200">
                                                    <div className="text-[11px] text-slate-400">Subject:</div>
                                                    <h5 className="font-bold text-slate-800 text-xs mt-0.5">
                                                        {financeState.midnight_audit_run.integrations.outlook.subject}
                                                    </h5>
                                                    <div className="flex justify-between text-[10px] text-slate-400 mt-2">
                                                        <div>
                                                            From: <strong className="text-slate-700">Dominique's Twin</strong> &lt;twin@solariagroup.com&gt;
                                                        </div>
                                                        <span>Just now</span>
                                                    </div>
                                                </div>
                                                <div className="p-4 bg-slate-50 flex-1 overflow-y-auto max-h-[220px]">
                                                    <div 
                                                        className="scale-[0.85] origin-top bg-white border border-slate-200 rounded-lg p-3 shadow-sm font-sans"
                                                        dangerouslySetInnerHTML={{ __html: financeState.midnight_audit_run.integrations.outlook.html_body }}
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {/* WHATSAPP NOTIFICATION MOCKUP */}
                                        {activePlatformAlert === 'whatsapp' && (
                                            <div className="flex-1 flex flex-col bg-slate-900 text-slate-300 font-sans text-xs">
                                                <div className="bg-slate-950 p-3 border-b border-slate-850 flex items-center gap-2">
                                                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                                                    <span className="font-bold text-slate-200 text-xs">Dominique CFO Twin (WhatsApp)</span>
                                                </div>
                                                <div className="flex-1 p-3 flex flex-col justify-end bg-slate-950 space-y-3">
                                                    <div className="max-w-[85%] self-start bg-emerald-950/80 border border-emerald-900/50 rounded-2xl rounded-tl-none p-3 shadow-md space-y-1 relative text-slate-200">
                                                        <div className="text-[11px] whitespace-pre-wrap leading-relaxed">
                                                            📱 <strong>Dominique's Twin Midnight Audit Summary</strong><br/><br/>
                                                            🚨 <strong>Solaria Ledger Review completed with 2 alerts.</strong><br/><br/>
                                                            ❌ <strong>Critical (IFRS IAS 38)</strong>: Capitalized Research Costs (EUR 45,000) under asset must be expensed in parent_nv.<br/>
                                                            ⚠️ <strong>Warning</strong>: Intercompany ledger mismatch between Parent NV and Flanders BV of <strong>EUR 2,000</strong>.<br/><br/>
                                                            👉 Click here to review the Command Center Dashboard: <span className="underline text-sky-400">http://localhost:3000</span>
                                                        </div>
                                                        <div className="text-[9px] text-slate-400 text-right mt-1.5">
                                                            {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} ✓✓
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}

                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

            </div>

            {/* Dynamic A2UI Surface Slider Panel */}
            {activeA2UISurface && activeA2UISurface.components && activeA2UISurface.components.length > 0 && (
                <div className="border-t border-emerald-500/30 bg-slate-950/90 p-5 space-y-4 animate-slideUp z-30">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-sans">
                                {activeA2UISurface.title || "Dynamic Financial Surface (A2UI)"}
                            </h3>
                        </div>
                        <span className="text-[9px] font-mono font-bold uppercase tracking-widest bg-emerald-950 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
                            A2UI Protocol Active
                        </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {activeA2UISurface.components.map((comp: any) => {
                            // Render individual component cards from the custom A2UI Catalog
                            
                            // A. KPI CARD
                            if (comp.type === "A2UIKpiCard") {
                                return (
                                    <div key={comp.id} className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center justify-between gap-4 shadow-lg hover:border-emerald-500/25 transition-all">
                                        <div className="space-y-0.5">
                                            <span className="text-[10px] text-slate-500 font-semibold uppercase">{comp.title}</span>
                                            <p className="text-2xl font-black font-mono text-slate-100">{comp.value}</p>
                                            {comp.subtitle && <p className="text-[10px] text-emerald-400 font-sans font-medium">{comp.subtitle}</p>}
                                        </div>
                                        <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl">
                                            <TrendingUp className="w-5 h-5" />
                                        </div>
                                    </div>
                                );
                            }

                            // B. AUDIT CHECKLIST
                            if (comp.type === "A2UIAuditChecklist") {
                                return (
                                    <div key={comp.id} className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl space-y-3 col-span-1 md:col-span-2 shadow-lg">
                                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">{comp.title}</h4>
                                        <div className="space-y-2">
                                            {(comp.items || []).map((item: any, idx: number) => {
                                                const isWarn = item.status === "warning";
                                                return (
                                                    <div key={idx} className={`p-3 rounded-lg border text-xs flex gap-3 ${
                                                        isWarn 
                                                            ? 'bg-rose-500/5 border-rose-500/20 text-slate-300' 
                                                            : 'bg-emerald-500/5 border-emerald-500/20 text-slate-300'
                                                    }`}>
                                                        {isWarn ? (
                                                            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                                                        ) : (
                                                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                                                        )}
                                                        <div className="space-y-0.5">
                                                            <span className={`font-bold ${isWarn ? 'text-rose-400' : 'text-emerald-400'}`}>{item.label}</span>
                                                            <p className="text-slate-400 font-sans mt-0.5 leading-relaxed">{item.details}</p>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            }

                            // C. GAUGE
                            if (comp.type === "A2UIGauge") {
                                const val = comp.value || 0;
                                const max = comp.max || 3.0;
                                const isHeal = comp.status === "Healthy";
                                const pct = Math.min((val / max) * 100, 100);
                                return (
                                    <div key={comp.id} className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center justify-between gap-4 shadow-lg hover:border-emerald-500/25 transition-all">
                                        <div className="space-y-1">
                                            <span className="text-[10px] text-slate-500 font-semibold uppercase">{comp.title}</span>
                                            <div className="flex items-baseline gap-1.5">
                                                <span className="text-2xl font-black font-mono text-slate-100">{val}</span>
                                                <span className="text-[10px] text-slate-500">/ {max}</span>
                                            </div>
                                            <span className={`inline-block px-1.5 py-0.5 text-[8px] font-sans font-bold uppercase tracking-wider rounded ${
                                                isHeal 
                                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                                                    : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                            }`}>
                                                {comp.status || 'Status Check'}
                                            </span>
                                        </div>
                                        {/* Radial SVG Gauge representation */}
                                        <div className="relative w-16 h-16 shrink-0 flex items-center justify-center">
                                            <svg className="w-full h-full transform -rotate-90">
                                                <circle cx="32" cy="32" r="28" className="stroke-slate-800 fill-none" strokeWidth="4" />
                                                <circle 
                                                    cx="32" 
                                                    cy="32" 
                                                    r="28" 
                                                    className={`fill-none transition-all duration-500 ${isHeal ? 'stroke-emerald-500' : 'stroke-amber-400'}`} 
                                                    strokeWidth="4" 
                                                    strokeDasharray={`${2 * Math.PI * 28}`}
                                                    strokeDashoffset={`${2 * Math.PI * 28 * (1 - pct/100)}`}
                                                />
                                            </svg>
                                            <span className="absolute text-[10px] font-black font-mono text-slate-300">{Math.round(pct)}%</span>
                                        </div>
                                    </div>
                                );
                            }

                            // D. VARIANCE CHART
                            if (comp.type === "A2UIVarianceChart") {
                                return (
                                    <div key={comp.id} className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl space-y-3 col-span-1 md:col-span-2 shadow-lg">
                                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">{comp.title}</h4>
                                        <div className="space-y-3">
                                            {(comp.series || []).map((ser: any, idx: number) => {
                                                const maxVal = Math.max(ser.actual, ser.budget, 1);
                                                const actPct = (ser.actual / maxVal) * 100;
                                                const budPct = (ser.budget / maxVal) * 100;
                                                const isFav = ser.variance >= 0;
                                                return (
                                                    <div key={idx} className="space-y-1 text-xs">
                                                        <div className="flex justify-between items-center text-slate-300">
                                                            <span className="font-bold font-mono">{ser.category}</span>
                                                            <span className={`font-mono font-bold ${isFav ? 'text-emerald-400' : 'text-rose-450'}`}>
                                                                Var: {isFav ? '+' : ''}{formatCurrency(ser.variance)}
                                                            </span>
                                                        </div>
                                                        <div className="space-y-1.5 font-sans text-[10px] text-slate-400 bg-slate-950/30 p-2 rounded border border-slate-900">
                                                            {/* Actual Row */}
                                                            <div className="space-y-0.5">
                                                                <div className="flex justify-between">
                                                                    <span>Actual:</span>
                                                                    <span className="font-bold text-slate-200">{formatCurrency(ser.actual)}</span>
                                                                </div>
                                                                <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden">
                                                                    <div className="h-full rounded-full bg-emerald-500" style={{ width: `${actPct}%` }} />
                                                                </div>
                                                            </div>
                                                            {/* Budget Row */}
                                                            <div className="space-y-0.5">
                                                                <div className="flex justify-between">
                                                                    <span>Budget:</span>
                                                                    <span className="font-bold text-slate-200">{formatCurrency(ser.budget)}</span>
                                                                </div>
                                                                <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden">
                                                                    <div className="h-full rounded-full bg-slate-650" style={{ width: `${budPct}%` }} />
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            }

                            // E. DATAGRID
                            if (comp.type === "A2UIDatagrid") {
                                const columns = comp.columns || [];
                                const rows = comp.rows || [];
                                return (
                                    <div key={comp.id} className="p-4 bg-slate-900/50 border border-slate-800 rounded-xl space-y-3 col-span-1 md:col-span-2 shadow-lg overflow-x-auto">
                                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">{comp.title}</h4>
                                        <div className="border border-slate-800 rounded-lg overflow-hidden min-w-[300px]">
                                            <table className="w-full text-left border-collapse text-[11px] font-mono">
                                                <thead>
                                                    <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                                                        {columns.map((c: string, cIdx: number) => (
                                                            <th key={cIdx} className="p-2">{c}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {rows.map((row: any, rIdx: number) => (
                                                        <tr key={rIdx} className="hover:bg-slate-850 border-b border-slate-850/60 text-slate-300">
                                                            {columns.map((c: string, cIdx: number) => (
                                                                <td key={cIdx} className="p-2">{row[c] !== undefined ? row[c] : '—'}</td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                );
                            }

                            return null;
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}

const MemoizedFinanceDashboard = React.memo(FinanceDashboard);
MemoizedFinanceDashboard.displayName = 'FinanceDashboard';

export default MemoizedFinanceDashboard;
