import { useState } from "react";
import { useListWorkspaces, useListFindings, useDeleteFinding, getListFindingsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { AlertTriangle, Trash2, Search, Filter } from "lucide-react";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { StatusBorder, StatusDot, statusFromSeverity } from "@/components/status-border";
import { MatrixText } from "@/components/matrix-text";

const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low: "bg-primary/15 text-primary border-primary/30",
  info: "bg-muted text-muted-foreground border-border",
};

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function WorkspaceFindings({ workspaceId, workspaceName, searchTerm, severity, status }: {
  workspaceId: string; workspaceName: string; searchTerm: string; severity: string; status: string;
}) {
  const queryClient = useQueryClient();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { data: findings, isLoading } = useListFindings(workspaceId, { query: { enabled: !!workspaceId, queryKey: getListFindingsQueryKey(workspaceId) } });
  const deleteFinding = useDeleteFinding();

  const filtered = findings?.filter(f => {
    if (searchTerm && !f.title.toLowerCase().includes(searchTerm.toLowerCase()) && !(f.affectedComponent?.toLowerCase().includes(searchTerm.toLowerCase()))) return false;
    if (severity !== "all" && f.severity !== severity) return false;
    if (status !== "all" && f.status !== status) return false;
    return true;
  }).sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9));

  if (isLoading) return <div className="space-y-2 mb-4">{Array.from({length:2}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>;
  if (!filtered?.length) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
        <span>{workspaceName}</span>
        <Badge variant="outline" className="text-xs">{filtered.length}</Badge>
      </h3>
      <div className="space-y-1.5">
        {filtered.map(f => (
          <StatusBorder key={f.id} status={statusFromSeverity(f.severity)} className="px-4 py-2.5 glass-card hover:brightness-110 transition-all cursor-default" showPulse={f.severity === "critical" || f.severity === "high"} data-testid={`row-finding-${f.id}`}>
            <div className="flex items-center gap-3 group">
            <StatusDot status={statusFromSeverity(f.severity)} />
            <Badge variant="outline" className={cn("text-xs capitalize flex-shrink-0 w-16 justify-center", SEV_COLORS[f.severity])}>
              {f.severity}
            </Badge>
            <div className="flex-1 min-w-0">
              <MatrixText text={f.title} className="font-medium text-sm" duration={400} />
              {f.affectedComponent && <span className="text-xs text-muted-foreground font-mono ml-2">{f.affectedComponent}</span>}
            </div>
            <Badge variant="outline" className="text-xs capitalize hidden sm:flex">{f.status}</Badge>
            {f.cve && <span className="text-xs font-mono text-muted-foreground hidden md:block">{f.cve}</span>}
            <span className="text-xs text-muted-foreground hidden lg:block">{format(new Date(f.createdAt), "MMM d")}</span>
            <Button
              variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive flex-shrink-0"
              onClick={() => setDeleteId(f.id)}
              data-testid={`button-delete-finding-${f.id}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
            </div>
          </StatusBorder>
        ))}
      </div>

      <AlertDialog open={!!deleteId} onOpenChange={open => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Finding?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteId) return;
              deleteFinding.mutate({ params: { workspaceId, findingId: deleteId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListFindingsQueryKey(workspaceId) }); setDeleteId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Findings() {
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const { data: workspaces, isLoading } = useListWorkspaces();

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <AlertTriangle className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Findings</h1>
            <p className="text-sm text-muted-foreground">All findings across workspaces</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search findings..."
              className="pl-8"
              value={search}
              onChange={e => setSearch(e.target.value)}
              data-testid="input-findings-search"
            />
          </div>
          <Select value={severity} onValueChange={setSeverity}>
            <SelectTrigger className="w-32" data-testid="select-severity-filter">
              <Filter className="h-3.5 w-3.5 mr-1.5" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severities</SelectItem>
              {["critical","high","medium","low","info"].map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-36" data-testid="select-status-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              {["open","confirmed","false-positive","remediated"].map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:4}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !workspaces?.length ? (
          <div className="text-center py-20 text-muted-foreground">
            No workspaces found. Create a workspace to start tracking findings.
          </div>
        ) : (
          workspaces.map(ws => (
            <WorkspaceFindings key={ws.id} workspaceId={ws.id} workspaceName={ws.name} searchTerm={search} severity={severity} status={status} />
          ))
        )}
      </div>
    </Layout>
  );
}
