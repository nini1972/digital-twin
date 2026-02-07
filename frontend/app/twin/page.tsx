"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";

export default function LandingPage() {
  const router = useRouter();
  const [isEntering, setIsEntering] = useState(false);
  const [showUI, setShowUI] = useState(false);
  const ambientRef = useRef<{ stop: () => void } | null>(null);

  useEffect(() => {
    if (!isEntering) return;
    const timer = setTimeout(() => {
      // stop ambient before navigating
      ambientRef.current?.stop();
      void router.push("/twin");
    }, 600);
    return () => clearTimeout(timer);
  }, [isEntering, router]);

  // Reveal UI after the video finishes (with a fallback in case onEnded doesn't fire)
  useEffect(() => {
    const fallback = setTimeout(() => setShowUI(true), 9000);
    return () => clearTimeout(fallback);
  }, []);

  // Start a lightweight ambient pad using Web Audio when the UI is revealed
  useEffect(() => {
    if (!showUI) return;
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioCtx();
    const master = ctx.createGain();
    master.gain.value = 0.12;
    master.connect(ctx.destination);

    const createPad = (freq: number, type: OscillatorType) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const filter = ctx.createBiquadFilter();
      osc.type = type;
      osc.frequency.value = freq;
      osc.detune.value = (Math.random() - 0.5) * 10;
      gain.gain.value = 0.35;
      filter.type = "lowpass";
      filter.frequency.value = 1200;
      osc.connect(filter);
      filter.connect(gain);
      gain.connect(master);
      osc.start();
      return { osc, gain, filter };
    };

    const p1 = createPad(110, "sawtooth");
    const p2 = createPad(165, "triangle");

    // slow LFO to modulate filter for an evolving pad
    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    lfo.type = "sine";
    lfo.frequency.value = 0.04;
    lfoGain.gain.value = 450;
    lfo.connect(lfoGain);
    lfoGain.connect(p1.filter.frequency);
    lfo.start();

    // gentle randomized amplitude ramps every few seconds
    const interval = window.setInterval(() => {
      const now = ctx.currentTime;
      p1.gain.gain.linearRampToValueAtTime(0.2 + Math.random() * 0.4, now + 4);
      p2.gain.gain.linearRampToValueAtTime(0.1 + Math.random() * 0.35, now + 5);
    }, 5200);

    ambientRef.current = {
      stop: () => {
        try {
          clearInterval(interval);
          lfo.stop();
          p1.osc.stop();
          p2.osc.stop();
          ctx.close();
        } catch { }
        ambientRef.current = null;
      },
    };

    return () => {
      ambientRef.current?.stop();
    };
  }, [showUI]);

  return (
    <main className="relative h-screen w-full overflow-hidden bg-black text-white">
      {/* Background video (plays once); place digital-twin-hero.mp4 in /public */}
      <video
        className="absolute inset-0 h-full w-full object-cover opacity-90"
        autoPlay
        muted
        playsInline
        preload="auto"
        onEnded={() => setShowUI(true)}
      >
        <source src="/digital-twin-hero.mp4" type="video/mp4" />
      </video>

      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/45" />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center h-full text-center px-6">
        {showUI && (
          <>
            <p className="mt-8 text-lg font-semibold text-cyan-200 drop-shadow-[0_0_16px_rgba(120,220,255,0.6)]">
              Enter a space where your intelligence is mirrored, amplified, and brought to life.
            </p>

            {/* Spacer to keep center area clear of the video text */}
            <div className="flex-1" />

            {/* Subtle entry button */}
            <button
              onClick={() => setIsEntering(true)}
              className="mb-4 px-8 py-3 rounded-full border border-white/30 bg-white/10 backdrop-blur-md text-white/90 hover:bg-white/20 hover:border-white/50 transition-all shadow-[0_0_18px_rgba(120,220,255,0.35)]"
            >
              Enter the Room
            </button>

            {/* Backup link (optional) */}
            <Link href="/twin" className="text-sm text-white/70 hover:text-white mb-6">
              Having trouble? Go now →
            </Link>
          </>
        )}

        {isEntering && null}
      </div>
    </main>
  );
}