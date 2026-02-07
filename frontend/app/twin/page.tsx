"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";

export default function LandingPage() {
  const router = useRouter();
  const [isEntering, setIsEntering] = useState(false);
  const [showUI, setShowUI] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [audioUnlocked, setAudioUnlocked] = useState(false);

  useEffect(() => {
    if (!isEntering) return;
    const timer = setTimeout(() => {
      // stop audio before navigating
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      void router.push("/twin");
    }, 600);
    return () => clearTimeout(timer);
  }, [isEntering, router]);

  useEffect(() => {
    if (audioUnlocked) return;
    const unlock = async () => {
      try {
        if (audioRef.current) {
          await audioRef.current.play();
          audioRef.current.pause();
          setAudioUnlocked(true);
        }
      } catch { }
    };
    document.addEventListener("click", unlock, { once: true });
    document.addEventListener("touchstart", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
    return () => {
      document.removeEventListener("click", unlock);
      document.removeEventListener("touchstart", unlock);
      document.removeEventListener("keydown", unlock);
    };
  }, [audioUnlocked]);

  const playSyncedAudio = async () => {
    try {
      if (!audioRef.current || !videoRef.current) return;
      audioRef.current.currentTime = videoRef.current.currentTime || 0;
      await audioRef.current.play();
    } catch { }
  };

  return (
    <main className="relative h-screen w-full overflow-hidden bg-black text-white">
      {/* Background video (plays once); place digital-twin-hero.mp4 in /public */}
      <video
        ref={videoRef}
        className="absolute inset-0 h-full w-full object-cover opacity-90"
        autoPlay
        muted
        playsInline
        preload="auto"
        onEnded={() => setShowUI(true)}
        onPlay={playSyncedAudio}
      >
        <source src="/digital-twin-hero.mp4" type="video/mp4" />
      </video>

      <audio ref={audioRef} src="/digital-twin-sound.mp3" preload="auto" />

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
              onClick={() => {
                if (audioRef.current) {
                  audioRef.current.pause();
                  audioRef.current.currentTime = 0;
                }
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