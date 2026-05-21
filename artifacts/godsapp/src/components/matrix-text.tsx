import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";

const MATRIX_CHARS = "01アイウエオカキクケコサシスセソABCDEF!@#$%^&*<>[]{}|\\/?~";

function scrambleChar(): string {
  return MATRIX_CHARS[Math.floor(Math.random() * MATRIX_CHARS.length)];
}

interface UseMatrixScrambleOptions {
  duration?: number;
  revealDelay?: number;
}

export function useMatrixScramble(
  text: string,
  { duration = 600, revealDelay = 35 }: UseMatrixScrambleOptions = {}
) {
  const [display, setDisplay] = useState(text);
  const [isScrambling, setIsScrambling] = useState(false);
  const frameRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => { setDisplay(text); }, [text]);

  const startScramble = useCallback(() => {
    if (isScrambling) return;
    setIsScrambling(true);
    startRef.current = performance.now();

    const animate = (now: number) => {
      const elapsed = now - (startRef.current ?? now);
      const progress = Math.min(elapsed / duration, 1);
      const revealedCount = Math.floor(progress * text.length);

      const chars = text.split("").map((char, i) => {
        if (char === " ") return " ";
        if (i < revealedCount) return text[i];
        return scrambleChar();
      });

      setDisplay(chars.join(""));

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        setDisplay(text);
        setIsScrambling(false);
        frameRef.current = null;
      }
    };

    frameRef.current = requestAnimationFrame(animate);
  }, [text, duration, isScrambling]);

  const stopScramble = useCallback(() => {
    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    setDisplay(text);
    setIsScrambling(false);
  }, [text]);

  useEffect(() => {
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return { display, isScrambling, startScramble, stopScramble };
}

interface MatrixTextProps {
  text: string;
  className?: string;
  scrambleOnMount?: boolean;
  duration?: number;
  tag?: keyof JSX.IntrinsicElements;
  glowOnScramble?: boolean;
}

export function MatrixText({
  text,
  className,
  scrambleOnMount = false,
  duration = 500,
  tag: Tag = "span",
  glowOnScramble = true,
}: MatrixTextProps) {
  const { display, isScrambling, startScramble } = useMatrixScramble(text, { duration });

  useEffect(() => {
    if (scrambleOnMount) {
      const t = setTimeout(startScramble, 100);
      return () => clearTimeout(t);
    }
  }, [scrambleOnMount, startScramble]);

  return (
    <Tag
      className={cn(
        "font-mono transition-all duration-100 cursor-default",
        isScrambling && glowOnScramble && "text-primary drop-shadow-[0_0_6px_theme(colors.cyan.400)]",
        className
      )}
      onMouseEnter={startScramble}
    >
      {display}
    </Tag>
  );
}

interface MatrixNavLabelProps {
  text: string;
  isActive?: boolean;
  className?: string;
}

export function MatrixNavLabel({ text, isActive, className }: MatrixNavLabelProps) {
  const { display, isScrambling, startScramble } = useMatrixScramble(text, { duration: 400 });

  return (
    <span
      className={cn(
        "truncate transition-all duration-100 font-mono text-[13px] tracking-wide",
        isScrambling && "text-primary drop-shadow-[0_0_5px_theme(colors.cyan.400)]",
        isActive && !isScrambling && "text-primary",
        className
      )}
      onMouseEnter={startScramble}
    >
      {display}
    </span>
  );
}
