'use client';

import dynamic from 'next/dynamic';
import Image from 'next/image';
import { startTransition, useState, useRef, useEffect, useCallback } from 'react';
import { Send, Activity, Sparkles } from 'lucide-react';

const FinanceDashboard = dynamic(() => import('./finance-dashboard'), {
    ssr: false,
    loading: () => (
        <div className="flex h-full min-h-[400px] items-center justify-center rounded-2xl border border-slate-800 bg-slate-950 text-slate-400">
            <div className="text-center">
                <p className="text-sm font-semibold text-slate-200">Loading finance dashboard...</p>
                <p className="mt-1 text-xs text-slate-500">Deferring the heavy panel until the main chat is interactive.</p>
            </div>
        </div>
    )
});

const SUGGESTED_AUDITS = [
    {
        text: "Run a comprehensive compliance audit of the group and identify accounting violations.",
        label: "Audit compliance (IAS 38)"
    },
    {
        text: "Consolidate the books of Solaria Group for FY25 and show me the elimination journal entries.",
        label: "Consolidate Group Ledgers"
    },
    {
        text: "Can you analyze Solaria France SAS individual reports and check its ratios?",
        label: "View Subsidiary Ratios (France)"
    },
    {
        text: "Reduce the capitalized research costs in parent NV to 0 in FY25_actual to resolve the IAS 38 compliance issue and run audits.",
        label: "Adjust capitalized research (Direct update)"
    }
];

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

// Helper to parse A2UI payloads inside assistant responses
const parseA2UI = (text: string) => {
    if (!text) return null;
    try {
        // Look for ```a2ui ... ``` code block
        const regex = /```a2ui\s*([\s\S]*?)```/g;
        let match;
        let lastPayload = null;
        while ((match = regex.exec(text)) !== null) {
            const rawJson = match[1].trim();
            lastPayload = JSON.parse(rawJson);
        }
        return lastPayload;
    } catch (e) {
        console.error("Failed to parse streamed A2UI block:", e);
        return null;
    }
};

export default function Twin() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string>('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const avatarFadeOutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const avatarTiltRef = useRef<HTMLDivElement>(null);

    // AI Finance Specialist State
    const [financeState, setFinanceState] = useState<any>({
        active_tab: "reports",
        selected_company: "parent_nv",
        reports_data: {},
        consolidation_data: {},
        review_data: {},
        data_update_data: {},
        logs: []
    });
    const [activeA2UISurface, setActiveA2UISurface] = useState<any>(null);
    const [welcomePhase, setWelcomePhase] = useState<
        "text" | "fade" | "video" | "avatar" | "avatar-fade-out" | "hidden"
    >("text");

    // Fetch the active financial state from the backend
    const fetchFinanceState = async () => {
        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiUrl}/api/finance/state`);
            if (res.ok) {
                const data = await res.json();
                startTransition(() => {
                    setFinanceState(data);
                });
            }
        } catch (err) {
            console.error("Error fetching financial state from API:", err);
        }
    };

    // Reset the financial state back to baseline
    const resetFinanceState = async () => {
        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const res = await fetch(`${apiUrl}/api/finance/reset`, { method: 'POST' });
            if (res.ok) {
                await fetchFinanceState();
                setActiveA2UISurface(null);
                setMessages(prev => [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: "I have successfully reset the Solaria Group trial balances and multi-agent logs back to their original mathematical baseline. How shall we begin our corporate review?",
                        timestamp: new Date()
                    }
                ]);
            }
        } catch (err) {
            console.error("Error resetting financial state:", err);
        }
    };

    // Sync financial state on initial load
    useEffect(() => {
        let timeoutId: ReturnType<typeof setTimeout> | null = null;
        let idleId: number | null = null;

        const loadFinanceState = () => {
            void fetchFinanceState();
        };

        if ('requestIdleCallback' in window) {
            idleId = window.requestIdleCallback(loadFinanceState, { timeout: 1200 });
        } else {
            timeoutId = setTimeout(loadFinanceState, 250);
        }

        return () => {
            if (idleId !== null && 'cancelIdleCallback' in window) {
                window.cancelIdleCallback(idleId);
            }
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        };
    }, []);

    // 3D Parallax Tilt Effect for Avatar Card
    useEffect(() => {
        if (welcomePhase !== 'avatar') {
            if (avatarTiltRef.current) {
                avatarTiltRef.current.style.transform = 'rotateY(0deg) rotateX(0deg)';
            }
            return;
        }

        let frameId = 0;
        const handleMouseMove = (e: MouseEvent) => {
            if (frameId) {
                cancelAnimationFrame(frameId);
            }

            frameId = requestAnimationFrame(() => {
                const x = (window.innerWidth / 2 - e.clientX) / 45;
                const y = (window.innerHeight / 2 - e.clientY) / 45;
                if (avatarTiltRef.current) {
                    avatarTiltRef.current.style.transform = `rotateY(${-x}deg) rotateX(${y}deg)`;
                }
            });
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => {
            if (frameId) {
                cancelAnimationFrame(frameId);
            }
            window.removeEventListener('mousemove', handleMouseMove);
        };
    }, [welcomePhase]);

    // Scroll to bottom of message list
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }, [messages]);

    // Fade-out welcome avatar
    const fadeOutWelcomeAvatar = useCallback(() => {
        if (welcomePhase === "hidden" || welcomePhase === "avatar-fade-out") return;

        if (
            welcomePhase === "text" ||
            welcomePhase === "fade" ||
            welcomePhase === "video"
        ) {
            setWelcomePhase("avatar");
        }

        setWelcomePhase("avatar-fade-out");

        if (avatarFadeOutTimerRef.current) {
            clearTimeout(avatarFadeOutTimerRef.current);
        }

        avatarFadeOutTimerRef.current = setTimeout(() => {
            setWelcomePhase("hidden");
            avatarFadeOutTimerRef.current = null;
        }, 700);
    }, [welcomePhase]);

    // Welcome transition sequence
    useEffect(() => {
        const fadeTimer = setTimeout(() => {
            setWelcomePhase("fade");
        }, 2200);

        const videoTimer = setTimeout(() => {
            setWelcomePhase("video");
        }, 2900);

        return () => {
            clearTimeout(fadeTimer);
            clearTimeout(videoTimer);
        };
    }, []);

    // Parse incoming assistant messages for A2UI blocks to sync the dashboard
    useEffect(() => {
        if (messages.length === 0) return;
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
            const payload = parseA2UI(lastMsg.content);
            if (payload) {
                setActiveA2UISurface(payload);
            }
        }
    }, [messages]);

    useEffect(() => {
        return () => {
            if (avatarFadeOutTimerRef.current) {
                clearTimeout(avatarFadeOutTimerRef.current);
            }
        };
    }, []);

    const sendMessage = async (messageText?: string) => {
        const textToSubmit = messageText || input;
        if (!textToSubmit.trim() || isLoading) return;

        fadeOutWelcomeAvatar();

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: textToSubmit,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        if (!messageText) setInput('');
        setIsLoading(true);

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${apiUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMessage.content,
                    session_id: sessionId || undefined,
                }),
            });

            if (!response.ok) throw new Error('Failed to submit message to LLM');

            const data = await response.json();

            if (!sessionId) {
                setSessionId(data.session_id);
            }

            // Strips out raw A2UI blocks from the displayed chat text so the conversational balloon looks super clean!
            let cleanedContent = data.response;
            cleanedContent = cleanedContent.replace(/```a2ui[\s\S]*?```/g, '').trim();

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: cleanedContent || "Task processed. Check the live visual control dashboard for updated metrics.",
                timestamp: new Date(),
            };

            setMessages(prev => [...prev, assistantMessage]);
            
            // Sync financial state instantly to display any database/calculation updates on the dashboard!
            await fetchFinanceState();

        } catch (error) {
            console.error('Error submitting chat:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'Forgive me, but I encountered a network discrepancy. Let me verify the server connection and try again.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const handleSuggestionClick = (suggestion: string) => {
        sendMessage(suggestion);
    };

    return (
        <div className="flex flex-col lg:flex-row h-full w-full bg-slate-950 text-slate-100 gap-5 overflow-hidden">
            
            {/* LEFT-PANE: Chat Assistant (40% width on LG screen) */}
            <div className="w-full lg:w-[38%] xl:w-[35%] flex flex-col h-full bg-slate-900/35 border border-slate-800/80 rounded-2xl overflow-hidden backdrop-blur-md shadow-2xl relative">
                
                {/* Header */}
                <div className="relative bg-slate-900 border-b border-slate-800/80 p-4 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="relative">
                            <Image
                                src="/favicon-180v2.png"
                                alt="Brand Icon"
                                width={40}
                                height={40}
                                className="w-10 h-10 rounded-xl shadow-[0_0_12px_rgba(16,185,129,0.3)] border border-emerald-500/20"
                                priority
                            />
                            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 border-2 border-slate-950 rounded-full" />
                        </div>
                        <div>
                            <h2 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
                                Dominique Twin <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                            </h2>
                            <p className="text-[11px] text-emerald-400 font-medium tracking-wide">
                                Corporate Finance Specialist Command
                            </p>
                        </div>
                    </div>
                </div>

                {/* Welcome Animations Zone */}
                {(welcomePhase === "text" || welcomePhase === "fade") && (
                    <div
                        className={`text-center text-slate-400 mt-20 welcome-slide-up select-none p-6 ${
                            welcomePhase === "fade" ? "welcome-fade" : "welcome-visible"
                        }`}
                    >
                        <p className="text-base font-bold text-slate-200">
                            Welcome to the Solaria Group Corporate Intelligence Center.
                        </p>
                        <p className="text-xs mt-2 text-slate-400 leading-relaxed max-w-xs mx-auto">
                            I am Dominique&apos;s AI Mirror. I coordinate our Scout, Consolidator, and Auditor agents to reviews books, consolidate financials, and evaluate compliance.
                        </p>
                    </div>
                )}

                {welcomePhase === "video" && (
                    <div className="flex justify-center mt-12 shrink-0">
                        <video
                            src="/avatar-blink.mp4"
                            autoPlay
                            muted
                            playsInline
                            className="w-24 h-24 rounded-full border border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.3)] avatar-fade-in"
                            onEnded={() => setWelcomePhase("avatar")}
                        />
                    </div>
                )}

                {welcomePhase === "avatar" && (
                    <div className="avatar-tilt-stage flex justify-center mt-12 shrink-0">
                        <div 
                            ref={avatarTiltRef}
                            className="avatar-tilt-card transition-transform duration-75 ease-out"
                        >
                            <Image
                                src="/avatar.png"
                                alt="Dominique Avatar"
                                width={112}
                                height={112}
                                className="w-24 h-24 rounded-full border border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.3)] avatar-fade-in avatar-breath"
                                priority
                            />
                        </div>
                    </div>
                )}

                {welcomePhase === "avatar-fade-out" && (
                    <div className="flex justify-center mt-12 shrink-0">
                        <Image
                            src="/avatar.png"
                            alt="Dominique Avatar"
                            width={112}
                            height={112}
                            className="w-24 h-24 rounded-full border border-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.3)] avatar-fade-out"
                            priority
                        />
                    </div>
                )}

                {/* Suggestion Prompts on Startup */}
                {messages.length === 0 && welcomePhase === "hidden" && (
                    <div className="flex-1 flex flex-col justify-center px-6 py-4 space-y-4">
                        <div className="flex items-center gap-2 mb-1">
                            <Activity className="w-4 h-4 text-emerald-400 shrink-0" />
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Suggested Financial Audits</h3>
                        </div>
                        <div className="grid grid-cols-1 gap-2.5">
                            {SUGGESTED_AUDITS.map((sug, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleSuggestionClick(sug.text)}
                                    className="p-3 bg-slate-900/60 border border-slate-800/80 hover:border-emerald-500/30 text-left rounded-xl hover:bg-slate-850 cursor-pointer group transition-all text-xs space-y-1"
                                >
                                    <span className="font-bold text-emerald-400 group-hover:text-emerald-300 transition-colors flex items-center justify-between">
                                        {sug.label}
                                        <Sparkles className="w-3 h-3 text-slate-500 group-hover:text-emerald-400 transition-colors" />
                                    </span>
                                    <p className="text-slate-400 group-hover:text-slate-300 line-clamp-1">{sug.text}</p>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Messages Box */}
                {welcomePhase === "hidden" && messages.length > 0 && (
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {messages.map((message, index) => (
                            <div
                                key={message.id}
                                ref={index === messages.length - 1 ? messagesEndRef : null}
                                className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                {message.role === 'assistant' ? (
                                    <>
                                        <div className="shrink-0">
                                            <Image
                                                src="/avatar.png"
                                                alt="Dominique Avatar"
                                                width={40}
                                                height={40}
                                                className="w-10 h-10 rounded-full border border-slate-800 shadow-[0_0_12px_rgba(16,185,129,0.25)]"
                                            />
                                        </div>

                                        <div className="max-w-[80%] rounded-2xl p-3.5 bg-slate-850 border border-slate-800 text-slate-200 shadow-md">
                                            <div className="prose prose-invert prose-xs text-xs whitespace-pre-wrap leading-relaxed">
                                                {message.content}
                                            </div>
                                            <p className="text-[9px] font-mono mt-2 text-slate-500 text-right">
                                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </p>
                                        </div>
                                    </>
                                ) : (
                                    <div className="max-w-[80%] rounded-2xl p-3.5 bg-emerald-500/10 border border-emerald-500/20 text-slate-100 shadow-md">
                                        <p className="whitespace-pre-wrap text-xs leading-relaxed">{message.content}</p>
                                        <p className="text-[9px] font-mono mt-2 text-emerald-500/60 text-right">
                                            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </p>
                                    </div>
                                )}
                            </div>
                        ))}

                        {isLoading && (
                            <div className="flex gap-3 justify-start">
                                <div className="shrink-0">
                                    <Image
                                        src="/avatar.png"
                                        alt="Dominique Avatar"
                                        width={40}
                                        height={40}
                                        className="w-10 h-10 rounded-full border border-slate-800 mr-1 shadow-[0_0_15px_rgba(16,185,129,0.6)] animate-pulse"
                                    />
                                </div>

                                <div className="bg-slate-850 border border-slate-800 rounded-2xl p-4 shadow-lg animate-pulse flex items-center justify-center">
                                    <div className="flex space-x-1.5">
                                        <div className="w-1.5 h-1.5 rounded-full animate-bounce bg-emerald-400" />
                                        <div className="w-1.5 h-1.5 rounded-full animate-bounce delay-100 bg-teal-400" />
                                        <div className="w-1.5 h-1.5 rounded-full animate-bounce delay-200 bg-cyan-400" />
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Input Tray */}
                <div className="border-t border-slate-800/80 p-4 bg-slate-900/40 shrink-0">
                    <div className="flex gap-2 relative">
                        <input
                            ref={inputRef}
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyPress}
                            placeholder="Instruct AI CFO twin..."
                            className="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 text-xs text-slate-100 disabled:opacity-50"
                            disabled={isLoading}
                            autoFocus
                        />
                        <button
                            onClick={() => sendMessage()}
                            disabled={!input.trim() || isLoading}
                            title="Send message"
                            className="px-4 py-2.5 bg-emerald-500 text-slate-950 hover:bg-emerald-400 rounded-xl font-bold text-xs disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-[0_0_15px_rgba(16,185,129,0.25)] hover:scale-105 active:scale-95 cursor-pointer flex items-center justify-center"
                        >
                            <Send className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            {/* RIGHT-PANE: Financial Intelligence Dashboard (60% width on LG screen) */}
            <div className="flex-1 h-full min-h-[400px]">
                <FinanceDashboard 
                    financeState={financeState}
                    activeA2UISurface={activeA2UISurface}
                    onReset={resetFinanceState}
                    onRefresh={fetchFinanceState}
                />
            </div>
            
        </div>
    );
}