"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function LandingPage() {
  const router = useRouter();
  const [isEntering, setIsEntering] = useState(false);

  useEffect(() => {
    if (!isEntering) return;
    const timer = setTimeout(() => {
      void router.push("/twin");
    }, 600);
    return () => clearTimeout(timer);
  }, [isEntering, router]);

  return (
    <main className="relative h-screen w-full overflow-hidden bg-black text-white">

      {/* Background image */}
      <div className="absolute inset-0">
        <img
          src="/digital-twin-hero.png"
          alt="Digital Twin Motion Art"
          className="h-full w-full object-cover opacity-80"
        />
      </div>

      {/* Dark overlay */}
      <div className="absolute inset-0 bg-black/40" />

      {/* Centered content */}
      <div className="relative z-10 flex flex-col items-center justify-center h-full text-center px-6">

        <h1 className="text-5xl font-bold tracking-wide mb-4">
          A WOMAN AND HER DIGITAL TWIN
        </h1>

        <p className="text-lg text-gray-300 mb-12">
          Enter a space where your intelligence is mirrored, amplified, and brought to life.
        </p>

        {/* FUN DOOR */}
        <div
          onClick={() => setIsEntering(true)}
          className={`
            w-24 h-48 rounded-sm mb-12 cursor-pointer transition-all duration-700
            bg-white/20 border border-white/30
            hover:bg-white/30 hover:shadow-[0_0_25px_rgba(255,255,255,0.6)]
            ${isEntering ? "scale-150 opacity-0" : ""}
          `}
        />

        {/* Enter button (backup navigation) */}
        <Link href="/twin">
          <button className="px-8 py-3 border border-white/40 rounded-lg hover:border-white transition-all">
            Enter the Room
          </button>
        </Link>

        {/* Auto‑navigate after animation */}
        {isEntering && null}
      </div>
    </main>
  );
}