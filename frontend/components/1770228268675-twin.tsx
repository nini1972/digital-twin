'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export default function Twin() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string>('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    
    const [welcomePhase, setWelcomePhase] = useState<"text" | "video" | "avatar" | "hidden">("text");

    // sequence: text -> video -> avatar
    useEffect(() => {
        // 1) text visible for 2s, then fade out + switch to video
        const textTimer = setTimeout(() => {
            setWelcomePhase("video");
        }, 2000); // adjust duration as you like

        return () => clearTimeout(textTimer);
    }, []);

    useEffect(() => {
        if (messages.length > 0) {
            // user started chatting → hide entire welcome area
            setWelcomePhase("hidden");
        }
    }, [messages]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: userMessage.content,
                    session_id: sessionId || undefined,
                }),
            });

            if (!response.ok) throw new Error('Failed to send message');

            const data = await response.json();

            if (!sessionId) {
                setSessionId(data.session_id);
            }

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.response,
                timestamp: new Date(),
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Error:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: 'Sorry, I encountered an error. Please try again.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
            // Refocus the input after message is sent
            setTimeout(() => {
                inputRef.current?.focus();
            }, 100);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    // Check if avatar exists
    const [hasAvatar, setHasAvatar] = useState(false);
    useEffect(() => {
        // Check if avatar.png exists
        fetch('/avatar.png', { method: 'HEAD' })
            .then(res => setHasAvatar(res.ok))
            .catch(() => setHasAvatar(false));
    }, []);

    
    return (
        <div className="flex flex-col h-full bg-gray-50 rounded-lg shadow-lg">
            {/* Header */}
            <div className="relative bg-gradient-to-r from-slate-700 to-slate-800 text-white p-5 rounded-t-lg shadow-md">
                <div className="flex items-center gap-3">
                    <img
                        src="/favicon-180v2.png"
                        alt="Brand Icon"
                        className="w-9 h-9 rounded-md shadow-[0_0_10px_rgba(255,120,200,0.35)]"
                    />
                    <div>
                        <h2 className="text-2xl font-semibold tracking-wide">
                            AI Digital Twin
                        </h2>
                        <p className="text-sm text-slate-300 mt-0.5">
                            Where your experience meets AI clarity
                        </p>
                    </div>
                </div>

                {/* Accent line */}
                <div className="mt-4 h-[2px] w-full bg-gradient-to-r from-pink-400/40 to-purple-400/40 rounded-full"></div>
            </div>
            
            {/* Welcome area – only when no messages yet */}
            {welcomePhase !== "hidden" && messages.length === 0 && (
                <div className="flex flex-col items-center mt-14">
                    {welcomePhase === "text" && (
                        <div className="text-center text-gray-500 fade-out">
                            <p className="text-lg font-medium text-gray-700">
                                Hello! I'm your Digital Twin.
                            </p>
                            <p className="text-sm mt-2 text-gray-500">
                                Ask me anything about AI deployment.
                            </p>
                        </div>
                    )}

                    {welcomePhase === "video" && (
                        <video
                            src="/avatar-blink.mp4"
                            autoPlay
                            muted
                            playsInline
                            className="w-32 h-32 mt-4 rounded-full shadow-[0_0_20px_rgba(255,120,200,0.4)]"
                            onEnded={() => setWelcomePhase("avatar")}
                        />
                    )}

                    {welcomePhase === "avatar" && (
                        <img
                            src="/avatar.png"
                            alt="Digital Twin Avatar"
                            className="w-32 h-32 mt-4 rounded-full shadow-[0_0_20px_rgba(255,120,200,0.4)]"
                        />
                    )}
                </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'
                            }`}
                    >
                        {message.role === 'assistant' ? (
                            <>
                                <div className="flex-shrink-0">
    <img
        src="/avatar.png"
        alt="Digital Twin Avatar"
        className="w-12 h-12 rounded-full border border-slate-300 mr-1 shadow-[0_0_10px_rgba(255,120,200,0.4)]"
    />
</div>

                                <div className="p-[2px] rounded-3xl bg-gradient-to-r from-pink-400 to-purple-400 max-w-[70%]">
                                    <div className="bg-white rounded-3xl p-3 text-gray-800">
                                        <p className="whitespace-pre-wrap">{message.content}</p>
                                        <p className="text-xs mt-1 text-gray-500">
                                            {message.timestamp.toLocaleTimeString()}
                                        </p>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="max-w-[70%] rounded-3xl p-3 bg-slate-700 text-white">
                                <p className="whitespace-pre-wrap">{message.content}</p>
                                <p className="text-xs mt-1 text-slate-300">
                                    {message.timestamp.toLocaleTimeString()}
                                </p>
                            </div>
                        )}


                        {message.role === 'user' && (
                            <div className="flex-shrink-0">
                                <div className="w-12 h-12 bg-gray-600 rounded-full flex items-center justify-center">
                                    <User className="w-5 h-5 text-white" />
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {isLoading && (
                    <div className="flex gap-3 justify-start">
                        <div className="flex-shrink-0">
                            {hasAvatar ? (
                                <img
                                    src="/avatar.png"
                                    alt="Digital Twin Avatar"
                                    className="w-12 h-12 rounded-full border border-slate-300 mr-1 shadow-[0_0_10px_rgba(255,120,200,0.4)]"
                                />
                            ) : (
                                <div className="w-12 h-12 bg-slate-700 rounded-full flex items-center justify-center">
                                    <Bot className="w-5 h-5 text-white" />
                                </div>
                            )}
                        </div>
                        <div className="bg-white border border-gray-200 rounded-3xl p-3 shadow-[0_0_12px_rgba(255,120,200,0.35)] animate-pulse">
                            <div className="flex space-x-2">
                                <div className="w-2 h-2 rounded-full animate-bounce bg-gradient-to-br from-pink-400 to-purple-400" />
                                <div className="w-2 h-2 rounded-full animate-bounce delay-100 bg-gradient-to-br from-purple-400 to-pink-300" />
                                <div className="w-2 h-2 rounded-full animate-bounce delay-200 bg-gradient-to-br from-pink-300 to-purple-300" />
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-gray-200 p-4 bg-white rounded-b-lg">
                <div className="flex gap-2">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyPress}
                        placeholder="Type your message..."
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-600 focus:border-transparent text-gray-800"
                        disabled={isLoading}
                        autoFocus
                    />
                    <button
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading}
                        className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
}