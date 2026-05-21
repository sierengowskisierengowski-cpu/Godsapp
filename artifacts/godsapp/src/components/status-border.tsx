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
  [key: string]: unknown;
}

const STATUS_CONFIG: Record<StatusLevel, {
  border: string;
  glow: string;
  pulse: string;
  dot: string;
  dotColor: string;
  label: string;
}> = {
  idle:     { border: "border-border/40",                        glow: "",                                                                                          pulse: "",                         dot: "bg-muted-foreground/35",  dotColor: "text-muted-foreground",  label: "idle"     },
  running:  { border: "border-[rgba(224,196,148,0.65)]",         glow: "shadow-[0_0_0_1px_rgba(224,196,148,0.28),0_0_16px_rgba(224,196,148,0.12)]",                pulse: "animate-pulse-glow-cream", dot: "bg-[rgb(224,196,148)]",   dotColor: "text-[rgb(224,196,148)]", label: "running"  },
  success:  { border: "border-green-400/55",                     glow: "shadow-[0_0_0_1px_rgba(74,222,128,0.22),0_0_12px_rgba(74,222,128,0.10)]",                  pulse: "",                         dot: "bg-green-400",            dotColor: "text-green-400",          label: "complete" },
  info:     { border: "border-blue-400/45",                      glow: "shadow-[0_0_8px_rgba(96,165,250,0.10)]",                                                   pulse: "",                         dot: "bg-blue-400",             dotColor: "text-blue-400",           label: "info"     },
  warning:  { border: "border-yellow-400/55",                    glow: "shadow-[0_0_0_1px_rgba(250,204,21,0.22),0_0_14px_rgba(250,204,21,0.10)]",                  pulse: "animate-pulse-glow-yellow", dot: "bg-yellow-400",           dotColor: "text-yellow-400",         label: "warning"  },
  high:     { border: "border-orange-400/65",                    glow: "shadow-[0_0_0_1px_rgba(251,146,60,0.28),0_0_18px_rgba(251,146,60,0.15)]",                  pulse: "animate-pulse-glow-orange", dot: "bg-orange-400",           dotColor: "text-orange-400",         label: "high"     },
  critical: { border: "border-red-500/75",                       glow: "shadow-[0_0_0_1px_rgba(239,68,68,0.38),0_0_24px_rgba(239,68,68,0.22),0_0_48px_rgba(239,68,68,0.08)]", pulse: "animate-pulse-glow-red", dot: "bg-red-500",  dotColor: "text-red-400",            label: "CRITICAL" },
};

export function StatusBorder({ status, children, className, rounded = "rounded-lg", showPulse = true, ...rest }: StatusBorderProps) {
  const config = STATUS_CONFIG[status];
  return (
    <div
      {...rest}
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
          <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-70", config.dot)} />
        )}
        <span className={cn("relative inline-flex rounded-full h-2 w-2", config.dot)} />
      </span>
      {label && (
        <span className={cn(
          "text-[10px] font-mono font-semibold uppercase tracking-wider",
          config.dotColor,
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
