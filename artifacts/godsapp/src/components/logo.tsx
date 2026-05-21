import { useEffect, useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  showText?: boolean;
  className?: string;
  textClassName?: string;
  trigger?: unknown;
}

export function GodsAppLogo({ size = 32, showText = true, className, textClassName, trigger }: LogoProps) {
  const [zapLevel, setZapLevel] = useState<0 | 1 | 2 | 3>(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const randomTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const zap = useCallback((intensity: 0 | 1 | 2 | 3 = 2, duration = 600) => {
    setZapLevel(intensity);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setZapLevel(0), duration);
  }, []);

  // Random ambient pulses
  useEffect(() => {
    const scheduleNext = () => {
      const delay = 3000 + Math.random() * 9000;
      randomTimerRef.current = setTimeout(() => {
        zap(1, 400);
        scheduleNext();
      }, delay);
    };
    scheduleNext();
    return () => {
      if (randomTimerRef.current) clearTimeout(randomTimerRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [zap]);

  // Trigger zap on navigation/external events
  useEffect(() => {
    if (trigger !== undefined) zap(2, 700);
  }, [trigger, zap]);

  // Expose zap globally for other components to trigger
  useEffect(() => {
    (window as unknown as Record<string, unknown>).__godsAppZap = zap;
    return () => { delete (window as unknown as Record<string, unknown>).__godsAppZap; };
  }, [zap]);

  const glowIntensity = [0, 0.3, 0.7, 1][zapLevel];
  // Cream/ivory bolt: resting=warm gold, level1=ivory, level2=off-white cream, level3=pure white
  const boltColor = zapLevel === 0 ? "#d4b87a" : zapLevel === 1 ? "#e0c494" : zapLevel === 2 ? "#eeddbf" : "#ffffff";
  const boltFilter = zapLevel > 0
    ? `drop-shadow(0 0 ${4 + zapLevel * 5}px ${boltColor}) drop-shadow(0 0 ${2 + zapLevel * 3}px #c9a85c)`
    : "none";

  return (
    <div className={cn("flex items-center gap-2 select-none", className)}>
      <div
        className="relative cursor-pointer flex-shrink-0"
        style={{ width: size, height: size }}
        onClick={() => zap(3, 800)}
        title="GodsApp"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 100 100"
          fill="none"
          width={size}
          height={size}
          style={{ transition: "filter 0.15s ease", filter: boltFilter }}
        >
          {/* Cloud shadow/depth */}
          <path
            d="M18 67 Q14 67 12 63 Q10 59 13 55 Q11 51 14 48 Q17 45 21 46 Q22 39 28 36 Q35 33 41 37 Q44 31 51 29 Q59 27 65 33 Q70 30 76 34 Q82 38 81 45 Q87 45 89 51 Q91 58 86 62 Q83 66 78 66 Z"
            fill="#051520"
            transform="translate(1,1)"
            opacity="0.5"
          />
          {/* Cloud body */}
          <path
            d="M18 67 Q14 67 12 63 Q10 59 13 55 Q11 51 14 48 Q17 45 21 46 Q22 39 28 36 Q35 33 41 37 Q44 31 51 29 Q59 27 65 33 Q70 30 76 34 Q82 38 81 45 Q87 45 89 51 Q91 58 86 62 Q83 66 78 66 Z"
            fill="#1a1610"
            stroke="#3a2e1e"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          {/* Cloud highlight top edge — warm cream shimmer */}
          <path
            d="M41 37 Q44 31 51 29 Q59 27 65 33"
            stroke="#d4b87a"
            strokeWidth="1"
            opacity="0.38"
            strokeLinecap="round"
          />
          {/* Glow halo behind bolt when zapping */}
          {zapLevel > 0 && (
            <ellipse
              cx="54"
              cy="57"
              rx={10 + zapLevel * 6}
              ry={18 + zapLevel * 5}
              fill={boltColor}
              opacity={glowIntensity * 0.15}
              style={{ transition: "all 0.1s" }}
            />
          )}
          {/* Lightning bolt */}
          <polygon
            points="59,30 46,55 56,55 47,80 68,50 57,50"
            fill={boltColor}
            style={{ transition: "fill 0.1s ease" }}
          />
          {/* Bolt inner shine */}
          <polygon
            points="59,30 46,55 56,55 47,80 68,50 57,50"
            fill="none"
            stroke={zapLevel > 1 ? "#ffffff" : "#e8d5a8"}
            strokeWidth={zapLevel > 0 ? "1.5" : "0.8"}
            strokeLinejoin="round"
            opacity={zapLevel > 0 ? 0.75 : 0.30}
            style={{ transition: "all 0.1s" }}
          />
          {/* Spark dots at bolt tip when fully zapping */}
          {zapLevel >= 2 && (
            <>
              <circle cx="47" cy="80" r="2"   fill="#ffffff"  opacity="0.90" />
              <circle cx="43" cy="76" r="1.2" fill="#eeddbf"  opacity="0.75" />
              <circle cx="51" cy="84" r="1"   fill="#d4b87a"  opacity="0.65" />
            </>
          )}
        </svg>
      </div>

      {showText && (
        <span className={cn("font-bold tracking-wider text-foreground", textClassName)}>
          GODS<span className="text-primary">APP</span>
        </span>
      )}
    </div>
  );
}

export function triggerLogoZap(intensity: 1 | 2 | 3 = 2) {
  const fn = (window as unknown as Record<string, unknown>).__godsAppZap as ((i: 1 | 2 | 3) => void) | undefined;
  if (fn) fn(intensity);
}
