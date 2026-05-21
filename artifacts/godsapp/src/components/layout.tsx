import { useState } from "react";
import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useGetSession, useLockSession } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getGetSessionQueryKey } from "@workspace/api-client-react";
import { GodsAppLogo, triggerLogoZap } from "@/components/logo";
import { MatrixNavLabel } from "@/components/matrix-text";
import { CommandPalette } from "@/components/command-palette";
import { StatusDot } from "@/components/status-border";
import {
  LayoutDashboard, FolderOpen, Database,
  Network, Globe, Lock, Cpu,
  FileText, Calendar, Puzzle, Settings,
  ChevronRight, Menu, AlertTriangle,
  Binary, Search, Terminal, Command,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
  { label: "Workspaces", icon: FolderOpen, href: "/workspaces" },
  { type: "separator", label: "Tools" },
  { label: "Network Recon", icon: Network, href: "/tools/network" },
  { label: "Web Analysis", icon: Globe, href: "/tools/web" },
  { label: "Crypto & Encoding", icon: Binary, href: "/tools/crypto" },
  { label: "Exploitation", icon: Terminal, href: "/tools/exploitation" },
  { label: "Threat Intel", icon: Search, href: "/tools/intel" },
  { type: "separator", label: "Operations" },
  { label: "Findings", icon: AlertTriangle, href: "/findings" },
  { label: "Evidence Locker", icon: Database, href: "/evidence" },
  { label: "Reports", icon: FileText, href: "/reports" },
  { label: "Scheduler", icon: Calendar, href: "/scheduler" },
  { label: "Plugins", icon: Puzzle, href: "/plugins" },
  { type: "separator", label: "System" },
  { label: "Settings", icon: Settings, href: "/settings" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const queryClient = useQueryClient();
  const { data: session } = useGetSession({ query: { queryKey: getGetSessionQueryKey() } });
  const lockSession = useLockSession();

  const handleLock = () => {
    triggerLogoZap(3);
    lockSession.mutate({}, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetSessionQueryKey() });
        window.location.href = "/lock";
      }
    });
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <CommandPalette />

      {/* Sidebar */}
      <aside className={cn(
        "flex flex-col glass-sidebar border-r border-sidebar-border/40 transition-all duration-200 flex-shrink-0 relative z-20",
        collapsed ? "w-[52px]" : "w-[220px]"
      )}>
        {/* Logo */}
        <div className={cn(
          "flex items-center h-12 px-3 border-b border-sidebar-border/30 flex-shrink-0",
          collapsed ? "justify-center" : "justify-between"
        )}>
          {!collapsed && (
            <GodsAppLogo
              size={28}
              showText
              trigger={location}
              textClassName="text-sm"
            />
          )}
          {collapsed && (
            <GodsAppLogo size={26} showText={false} trigger={location} />
          )}
          <Button
            variant="ghost"
            size="icon"
            className={cn("h-7 w-7 text-muted-foreground hover:text-primary glass-hover", collapsed && "mx-auto mt-0")}
            onClick={() => setCollapsed(!collapsed)}
            data-testid="button-toggle-sidebar"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>

        {/* Nav */}
        <ScrollArea className="flex-1">
          <nav className="py-2 px-1.5">
            {NAV_ITEMS.map((item, i) => {
              if (item.type === "separator") {
                return (
                  <div key={i} className={cn("mt-3 mb-1", collapsed ? "px-1" : "px-1.5")}>
                    {!collapsed && (
                      <span className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground/40 px-1 font-mono">
                        {item.label}
                      </span>
                    )}
                    {collapsed && <Separator className="bg-sidebar-border/30" />}
                  </div>
                );
              }

              const Icon = item.icon!;
              const isActive = location === item.href || (item.href !== "/dashboard" && location.startsWith(item.href!));

              return (
                <Link key={item.href} href={item.href!}>
                  <a
                    data-testid={`nav-link-${item.label?.toLowerCase().replace(/\s+/g, "-")}`}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2 py-1.5 mb-0.5 transition-all duration-150 group relative",
                      collapsed ? "justify-center px-1.5" : "",
                      isActive
                        ? "bg-primary/10 border border-primary/20 shadow-[0_0_10px_rgba(224,196,148,0.10)]"
                        : "border border-transparent glass-hover"
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    {/* Active left accent bar */}
                    {isActive && !collapsed && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-primary shadow-[0_0_8px_rgba(224,196,148,0.80)]" />
                    )}
                    <Icon className={cn(
                      "h-4 w-4 flex-shrink-0 transition-all duration-150",
                      isActive ? "text-primary drop-shadow-[0_0_7px_rgba(224,196,148,0.75)]" : "text-muted-foreground group-hover:text-primary"
                    )} />
                    {!collapsed && (
                      <MatrixNavLabel
                        text={item.label!}
                        isActive={isActive}
                        className={cn(!isActive && "text-sidebar-foreground group-hover:text-primary")}
                      />
                    )}
                  </a>
                </Link>
              );
            })}
          </nav>
        </ScrollArea>

        {/* Bottom */}
        <div className={cn("p-2 border-t border-sidebar-border/30 space-y-1", collapsed ? "flex flex-col items-center" : "")}>
          {/* Cmd+K hint */}
          {!collapsed && (
            <button
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-muted-foreground/50 border border-border/20 glass-hover font-mono hover:text-primary transition-colors"
              onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
            >
              <Command className="h-3 w-3" />
              <span className="flex-1 text-left">Quick search</span>
              <kbd className="text-[10px] opacity-60">⌘K</kbd>
            </button>
          )}
          <Button
            variant="ghost"
            size={collapsed ? "icon" : "sm"}
            className={cn(
              "text-muted-foreground hover:text-red-400 hover:bg-red-400/5 transition-colors",
              collapsed ? "h-8 w-8" : "w-full justify-start gap-2 text-xs"
            )}
            onClick={handleLock}
            data-testid="button-lock-session"
          >
            <Lock className="h-3.5 w-3.5 flex-shrink-0" />
            {!collapsed && <span className="font-mono">Lock Session</span>}
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-12 border-b border-border/30 glass-topbar flex items-center justify-between px-4 flex-shrink-0 z-10">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground/60">~/godsapp</span>
            <span className="text-muted-foreground/30 text-xs">/</span>
            <span className="text-xs font-mono text-primary/80">
              {location.replace(/^\//, "") || "dashboard"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <StatusDot status="running" label />
            <span className="text-xs text-muted-foreground/50 font-mono hidden md:block">
              {session?.authenticated ? "authenticated" : "locked"}
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
