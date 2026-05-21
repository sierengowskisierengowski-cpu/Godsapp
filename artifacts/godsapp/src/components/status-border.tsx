import { cn } from "@/lib/utils";

export type StatusLevel =
  | "idle"
  | "running"
  | "success"
  | "warning"
  | "high"
  | "critical"
  | "info";

interface StatusBorderProps {
  status: StatusLevel;
  children: React.ReactNode;
  className?: string;
  rounded?: string;
  showPulse?: boolean;
}

const STATUS_CONFIG: Record<StatusLevel, {
  border: string;
  glow: string;
  pulse: string;
  dot: string;
  label: string;
}> = {
  idle:     { border: "border-border/50",                       glow: "",                                                                      pulse: "",                       dot: "bg-muted-foreground/40", label: "idle" },
  running:  { border: "border-cyan-400/70",                     glow: "shadow-[0_0_0_1px_rgba(34,211,238,0.3),0_0_16px_rgba(34,211,238,0.15)]", pulse: "animate-pulse-glow-cyan",  dot: "bg-cyan-400",            label: "running" },
  success:  { border: "border-green-400/60",                    glow: "shadow-[0_0_0_1px_rgba(74,222,128,0.25),0_0_12px_rgba(74,222,128,0.12)]", pulse: "",                       dot: "bg-green-400",           label: "complete" },
  info:     { border: "border-blue-400/50",                     glow: "shadow-[0_0_8px_rgba(96,165,250,0.12)]",                                pulse: "",                       dot: "bg-blue-400",            label: "info" },
  warning:  { border: "border-yellow-400/60",                   glow: "shadow-[0_0_0_1px_rgba(250,204,21,0.25),0_0_14px_rgba(250,204,21,0.12)]", pulse: "animate-pulse-glow-yellow", dot: "bg-yellow-400",          label: "warning" },
  high:     { border: "border-orange-400/70",                   glow: "shadow-[0_0_0_1px_rgba(251,146,60,0.3),0_0_18px_rgba(251,146,60,0.18)]",  pulse: "animate-pulse-glow-orange", dot: "bg-orange-400",          label: "high" },
  critical: { border: "border-red-500/80",                      glow: "shadow-[0_0_0_1px_rgba(239,68,68,0.4),0_0_24px_rgba(239,68,68,0.25),0_0_48px_rgba(239,68,68,0.1)]",       pulse: "animate-pulse-glow-red",   dot: "bg-red-500",             label: "CRITICAL" },
};

export function StatusBorder({ status, children, className, rounded = "rounded-lg", showPulse = true }: StatusBorderProps) {
  const config = STATUS_CONFIG[status];
  return (
    <div
      className={cn(
        "relative border transition-all duration-500",
        config.border,
        config.glow,
        showPulse && config.pulse,
        rounded,
        className
      )}
    >
      {children}
    </div>
  );
}

interface StatusDotProps {
  status: StatusLevel;
  className?: string;
  label?: boolean;
}

export function StatusDot({ status, className, label = false }: StatusDotProps) {
  const config = STATUS_CONFIG[status];
  const isPulsing = ["running", "critical", "high", "warning"].includes(status);
  return (
    <span className={cn("flex items-center gap-1.5", className)}>
      <span className="relative flex h-2 w-2">
        {isPulsing && (
          <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", config.dot)} />
        )}
        <span className={cn("relative inline-flex rounded-full h-2 w-2", config.dot)} />
      </span>
      {label && (
        <span className={cn(
          "text-[10px] font-mono font-semibold uppercase tracking-wider",
          status === "critical" && "text-red-400",
          status === "high" && "text-orange-400",
          status === "warning" && "text-yellow-400",
          status === "running" && "text-cyan-400",
          status === "success" && "text-green-400",
          status === "idle" && "text-muted-foreground",
          status === "info" && "text-blue-400",
        )}>
          {config.label}
        </span>
      )}
    </span>
  );
}

export function statusFromSeverity(severity: string): StatusLevel {
  switch (severity?.toLowerCase()) {
    case "critical": return "critical";
    case "high": return "high";
    case "medium": case "warning": return "warning";
    case "low": return "info";
    default: return "idle";
  }
}

export function statusFromScanStatus(scanStatus: string): StatusLevel {
  switch (scanStatus?.toLowerCase()) {
    case "running": return "running";
    case "completed": case "done": return "success";
    case "failed": case "error": return "critical";
    case "stopped": return "warning";
    default: return "idle";
  }
}
