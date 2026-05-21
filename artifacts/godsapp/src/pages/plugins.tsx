import { useListPlugins, useTogglePlugin, getListPluginsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Puzzle, Network, Globe, Lock, Cpu, Search, Terminal, Microscope } from "lucide-react";
import { cn } from "@/lib/utils";

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  network: Network,
  web: Globe,
  password: Lock,
  crypto: Cpu,
  osint: Search,
  exploitation: Terminal,
  forensics: Microscope,
  general: Puzzle,
};

const CATEGORY_COLORS: Record<string, string> = {
  network: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  web: "text-green-400 bg-green-500/10 border-green-500/20",
  password: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  crypto: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  osint: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  exploitation: "text-red-400 bg-red-500/10 border-red-500/20",
  forensics: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  general: "text-muted-foreground bg-muted border-border",
};

export default function Plugins() {
  const queryClient = useQueryClient();
  const { data: plugins, isLoading } = useListPlugins({ query: { queryKey: getListPluginsQueryKey() } });
  const togglePlugin = useTogglePlugin();

  const categories = [...new Set(plugins?.map(p => p.category) ?? [])].sort();

  const handleToggle = (id: string) => {
    togglePlugin.mutate({ params: { id } }, {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getListPluginsQueryKey() })
    });
  };

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Puzzle className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Plugins</h1>
            <p className="text-sm text-muted-foreground">Enable security tools and integrations</p>
          </div>
        </div>

        <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/20 mb-6 text-xs text-muted-foreground">
          <Puzzle className="h-4 w-4 text-primary flex-shrink-0" />
          <span>
            Plugin toggles track which tools are part of your assessment workflow.
            Tool availability depends on your system installation.
          </span>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:8}).map((_,i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : (
          categories.map(cat => {
            const catPlugins = plugins?.filter(p => p.category === cat) ?? [];
            const Icon = CATEGORY_ICONS[cat] ?? Puzzle;
            return (
              <div key={cat} className="mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider capitalize">{cat}</h3>
                  <span className="text-xs text-muted-foreground">({catPlugins.length})</span>
                </div>
                <div className="space-y-1.5">
                  {catPlugins.map(plugin => (
                    <div key={plugin.id} className="flex items-center gap-4 border border-border rounded-lg px-4 py-3 bg-card" data-testid={`row-plugin-${plugin.id}`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{plugin.name}</span>
                          <Badge variant="outline" className={cn("text-xs capitalize", CATEGORY_COLORS[plugin.category])}>
                            v{plugin.version}
                          </Badge>
                        </div>
                        {plugin.description && (
                          <p className="text-xs text-muted-foreground mt-0.5">{plugin.description}</p>
                        )}
                      </div>
                      {plugin.author && (
                        <span className="text-xs text-muted-foreground hidden md:block">by {plugin.author}</span>
                      )}
                      <Switch
                        checked={plugin.enabled}
                        onCheckedChange={() => handleToggle(plugin.id)}
                        disabled={togglePlugin.isPending}
                        data-testid={`switch-plugin-${plugin.id}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>
    </Layout>
  );
}
