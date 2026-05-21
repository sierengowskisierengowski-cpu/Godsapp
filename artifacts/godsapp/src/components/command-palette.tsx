import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { triggerLogoZap } from "@/components/logo";
import {
  LayoutDashboard, FolderOpen, Shield, Database,
  Network, Globe, Binary, Terminal, Search,
  FileText, Calendar, Puzzle, Settings, AlertTriangle,
  Command, ChevronRight,
} from "lucide-react";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  action?: () => void;
  badge?: string;
  badgeVariant?: "default" | "destructive" | "outline" | "secondary";
  group: string;
}

const COMMANDS: CommandItem[] = [
  { id: "dashboard", label: "Dashboard", description: "Operations overview", icon: LayoutDashboard, href: "/dashboard", group: "Navigation" },
  { id: "workspaces", label: "Workspaces", description: "Manage target workspaces", icon: FolderOpen, href: "/workspaces", group: "Navigation" },
  { id: "findings", label: "Findings", description: "Security findings", icon: AlertTriangle, href: "/findings", group: "Navigation" },
  { id: "evidence", label: "Evidence Locker", description: "Chain of custody", icon: Database, href: "/evidence", group: "Navigation" },
  { id: "reports", label: "Reports", description: "Generate security reports", icon: FileText, href: "/reports", group: "Navigation" },
  { id: "scheduler", label: "Scheduler", description: "Automated scan schedules", icon: Calendar, href: "/scheduler", group: "Navigation" },
  { id: "plugins", label: "Plugins", description: "Manage tool plugins", icon: Puzzle, href: "/plugins", group: "Navigation" },
  { id: "settings", label: "Settings", description: "App configuration & API keys", icon: Settings, href: "/settings", group: "Navigation" },
  { id: "tool-network", label: "Network Recon", description: "DNS, WHOIS lookups", icon: Network, href: "/tools/network", group: "Tools", badge: "tool" },
  { id: "tool-web", label: "Web Analysis", description: "SSL, headers, JWT", icon: Globe, href: "/tools/web", group: "Tools", badge: "tool" },
  { id: "tool-crypto", label: "Crypto & Encoding", description: "Hash, encode, identify", icon: Binary, href: "/tools/crypto", group: "Tools", badge: "tool" },
  { id: "tool-exploit", label: "Exploitation", description: "Reverse shells & payloads", icon: Terminal, href: "/tools/exploitation", group: "Tools", badge: "tool" },
  { id: "tool-intel", label: "Threat Intel", description: "IP intelligence, HIBP", icon: Search, href: "/tools/intel", group: "Tools", badge: "tool" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [, navigate] = useLocation();

  const filtered = query.trim()
    ? COMMANDS.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.description?.toLowerCase().includes(query.toLowerCase()) ||
        c.group.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS;

  const groups = [...new Set(filtered.map(c => c.group))];

  useEffect(() => { setSelected(0); }, [query]);

  const runCommand = useCallback((cmd: CommandItem) => {
    setOpen(false);
    setQuery("");
    triggerLogoZap(2);
    if (cmd.href) navigate(cmd.href);
    if (cmd.action) cmd.action();
  }, [navigate]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(prev => !prev);
        if (!open) triggerLogoZap(1);
        return;
      }
      if (!open) return;
      if (e.key === "ArrowDown") { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
      if (e.key === "Enter") { e.preventDefault(); if (filtered[selected]) runCommand(filtered[selected]); }
      if (e.key === "Escape") { setOpen(false); setQuery(""); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, selected, runCommand]);

  let itemIndex = 0;

  return (
    <>
      <Dialog open={open} onOpenChange={o => { setOpen(o); if (!o) setQuery(""); }}>
        <DialogContent className="p-0 gap-0 max-w-xl overflow-hidden border-primary/30 bg-background/95 backdrop-blur-xl shadow-2xl shadow-primary/10">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <Command className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <Input
              autoFocus
              placeholder="Search commands, tools, pages..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="border-0 bg-transparent shadow-none focus-visible:ring-0 px-0 text-sm placeholder:text-muted-foreground/60 h-auto py-0"
              data-testid="command-palette-input"
            />
            <kbd className="hidden md:inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-border bg-muted text-[10px] text-muted-foreground">
              ESC
            </kbd>
          </div>

          <div className="max-h-[380px] overflow-y-auto py-2">
            {filtered.length === 0 ? (
              <div className="text-center py-10 text-sm text-muted-foreground">No results for "{query}"</div>
            ) : (
              groups.map(group => {
                const groupItems = filtered.filter(c => c.group === group);
                return (
                  <div key={group}>
                    <div className="px-4 py-1.5">
                      <span className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground/60">{group}</span>
                    </div>
                    {groupItems.map(cmd => {
                      const idx = itemIndex++;
                      const Icon = cmd.icon;
                      const isSelected = idx === selected;
                      return (
                        <button
                          key={cmd.id}
                          className={cn(
                            "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                            isSelected ? "bg-primary/10 text-primary" : "hover:bg-accent text-foreground"
                          )}
                          onClick={() => runCommand(cmd)}
                          onMouseEnter={() => setSelected(idx)}
                          data-testid={`cmd-${cmd.id}`}
                        >
                          <Icon className={cn("h-4 w-4 flex-shrink-0", isSelected ? "text-primary" : "text-muted-foreground")} />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium leading-tight">{cmd.label}</div>
                            {cmd.description && <div className="text-xs text-muted-foreground truncate">{cmd.description}</div>}
                          </div>
                          {cmd.badge && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-muted-foreground">{cmd.badge}</Badge>
                          )}
                          {isSelected && <ChevronRight className="h-3 w-3 text-primary flex-shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>

          <div className="px-4 py-2 border-t border-border flex items-center gap-4 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded border border-border bg-muted">↑↓</kbd> navigate</span>
            <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded border border-border bg-muted">↵</kbd> open</span>
            <span className="flex items-center gap-1"><kbd className="px-1 py-0.5 rounded border border-border bg-muted">⌘K</kbd> toggle</span>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
