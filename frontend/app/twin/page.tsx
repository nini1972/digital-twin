"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";

export default function LandingPage() {
  const router = useRouter();
  const [isEntering, setIsEntering] = useState(false);
  const [showUI, setShowUI] = useState(false);
  const ambientRef = useRef<{ stop: () => void } | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const gestureListenersRef = useRef<() => void | null>(null);

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

  // Start a lightweight ambient pad using Web Audio when the UI is revealed,
  // but only actually initialize sound after a user gesture (resume).
  useEffect(() => {
    if (!showUI) return;

    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    const ctx = new AudioCtx();
    audioCtxRef.current = ctx;

    let intervalId: number | null = null;
    let lfo: OscillatorNode | null = null;

    const createPadNodes = (c: AudioContext) => {
      const master = c.createGain();
      master.gain.value = 0.12;
      master.connect(c.destination);

      const makePad = (freq: number, type: OscillatorType) => {
        const osc = c.createOscillator();
        const gain = c.createGain();
        const filter = c.createBiquadFilter();
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

      const p1 = makePad(110, "sawtooth");
      const p2 = makePad(165, "triangle");

      lfo = c.createOscillator();
      const lfoGain = c.createGain();
      lfo.type = "sine";
      lfo.frequency.value = 0.04;
      lfoGain.gain.value = 450;
      lfo.connect(lfoGain);
      lfoGain.connect((p1.filter as BiquadFilterNode).frequency);
      lfo.start();

      intervalId = window.setInterval(() => {
        const now = c.currentTime;
        p1.gain.gain.linearRampToValueAtTime(0.2 + Math.random() * 0.4, now + 4);
        p2.gain.gain.linearRampToValueAtTime(0.1 + Math.random() * 0.35, now + 5);
      }, 5200);

      ambientRef.current = {
        stop: () => {
          try {
            if (intervalId) clearInterval(intervalId);
            lfo?.stop();
            p1.osc.stop();
            p2.osc.stop();
            c.close();
          } catch { }
          ambientRef.current = null;
        },
      };
    };

    const resumeAndStart = async () => {
      try {
        if (!audioCtxRef.current) return;
        if (audioCtxRef.current.state === "suspended") {
          await audioCtxRef.current.resume();
        }
        if (!ambientRef.current) createPadNodes(audioCtxRef.current);
      } catch { }
      // remove gesture listeners after first resume
      removeGestureListeners();
    };

    const addGestureListeners = () => {
      const handler = () => void resumeAndStart();
      document.addEventListener("click", handler, { once: true });
      document.addEventListener("touchstart", handler, { once: true });
      document.addEventListener("keydown", handler, { once: true });
      gestureListenersRef.current = () => {
        document.removeEventListener("click", handler);
        document.removeEventListener("touchstart", handler);
        document.removeEventListener("keydown", handler);
      };
    };

    const removeGestureListeners = () => {
      gestureListenersRef.current?.();
      gestureListenersRef.current = null;
    };

    // If already running, start immediately; otherwise wait for gesture
    if (ctx.state === "running") {
      createPadNodes(ctx);
    } else {
      addGestureListeners();
    }

    return () => {
      removeGestureListeners();
      ambientRef.current?.stop();
      audioCtxRef.current = null;
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
              onClick={async () => {
                // ensure audio resumes on button click (user gesture) before navigating
                try {
                  if (audioCtxRef.current && audioCtxRef.current.state === "suspended") {
                    await audioCtxRef.current.resume();
                  }
                } catch { }
                setIsEntering(true);
              }}
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