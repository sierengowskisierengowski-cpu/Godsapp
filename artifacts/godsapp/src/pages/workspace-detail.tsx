import { useState } from "react";
import { useParams, useLocation } from "wouter";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  useGetWorkspace, useGetWorkspaceStats, useListScans, useListFindings, useListEvidence,
  useCreateScan, useCreateFinding, useDeleteScan, useDeleteFinding, useStopScan,
  getGetWorkspaceQueryKey, getGetWorkspaceStatsQueryKey, getListScansQueryKey, getListFindingsQueryKey, getListEvidenceQueryKey
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import {
  Plus, Trash2, Square, RotateCw, Target, Activity,
  AlertTriangle, Database, ChevronLeft, Shield
} from "lucide-react";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

const scanSchema = z.object({
  name: z.string().min(1, "Name required"),
  target: z.string().min(1, "Target required"),
  tool: z.string().min(1, "Tool required"),
});

const findingSchema = z.object({
  title: z.string().min(1, "Title required"),
  description: z.string().optional(),
  severity: z.string().default("info"),
  affectedComponent: z.string().optional(),
  recommendation: z.string().optional(),
});

type ScanForm = z.infer<typeof scanSchema>;
type FindingForm = z.infer<typeof findingSchema>;

const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low: "bg-primary/15 text-primary border-primary/30",
  info: "bg-muted text-muted-foreground border-border",
};

const SCAN_STATUS_COLORS: Record<string, string> = {
  pending: "bg-muted text-muted-foreground",
  running: "bg-primary/15 text-primary",
  completed: "bg-green-500/15 text-green-400",
  failed: "bg-red-500/15 text-red-400",
  stopped: "bg-orange-500/15 text-orange-400",
};

const TOOLS = ["nmap", "gobuster", "nikto", "sqlmap", "hydra", "custom"];

export default function WorkspaceDetail() {
  const { id } = useParams<{ id: string }>();
  const [, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const [showScanForm, setShowScanForm] = useState(false);
  const [showFindingForm, setShowFindingForm] = useState(false);
  const [deleteScanId, setDeleteScanId] = useState<string | null>(null);
  const [deleteFindingId, setDeleteFindingId] = useState<string | null>(null);

  const { data: workspace, isLoading: wsLoading } = useGetWorkspace(id!, { query: { enabled: !!id, queryKey: getGetWorkspaceQueryKey(id!) } });
  const { data: stats } = useGetWorkspaceStats(id!, { query: { enabled: !!id, queryKey: getGetWorkspaceStatsQueryKey(id!) } });
  const { data: scans } = useListScans(id!, { query: { enabled: !!id, queryKey: getListScansQueryKey(id!) } });
  const { data: findings } = useListFindings(id!, { query: { enabled: !!id, queryKey: getListFindingsQueryKey(id!) } });
  const { data: evidence } = useListEvidence(id!, { query: { enabled: !!id, queryKey: getListEvidenceQueryKey(id!) } });

  const createScan = useCreateScan();
  const createFinding = useCreateFinding();
  const deleteScan = useDeleteScan();
  const deleteFinding = useDeleteFinding();
  const stopScan = useStopScan();

  const scanForm = useForm<ScanForm>({ resolver: zodResolver(scanSchema), defaultValues: { name: "", target: "", tool: "nmap" } });
  const findingForm = useForm<FindingForm>({ resolver: zodResolver(findingSchema), defaultValues: { title: "", description: "", severity: "info", affectedComponent: "", recommendation: "" } });

  const onCreateScan = (data: ScanForm) => {
    createScan.mutate({ params: { workspaceId: id! }, data }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListScansQueryKey(id!) });
        setShowScanForm(false);
        scanForm.reset();
      }
    });
  };

  const onCreateFinding = (data: FindingForm) => {
    createFinding.mutate({ params: { workspaceId: id! }, data }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListFindingsQueryKey(id!) });
        queryClient.invalidateQueries({ queryKey: getGetWorkspaceStatsQueryKey(id!) });
        setShowFindingForm(false);
        findingForm.reset();
      }
    });
  };

  if (wsLoading) {
    return <Layout><div className="p-6 space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-40" /></div></Layout>;
  }

  if (!workspace) {
    return <Layout><div className="p-6 text-center text-muted-foreground">Workspace not found</div></Layout>;
  }

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-start gap-4 mb-6">
          <Button variant="ghost" size="icon" className="h-8 w-8 mt-0.5 flex-shrink-0" onClick={() => setLocation("/workspaces")}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-bold">{workspace.name}</h1>
              <Badge variant="outline" className="text-xs capitalize">{workspace.type}</Badge>
            </div>
            {workspace.target && (
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Target className="h-3.5 w-3.5" />
                <span className="font-mono">{workspace.target}</span>
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
          {[
            { label: "Scans", value: stats?.scans ?? 0, icon: Activity, color: "text-primary" },
            { label: "Findings", value: stats?.findings ?? 0, icon: Shield, color: "text-foreground" },
            { label: "Critical", value: stats?.critical ?? 0, icon: AlertTriangle, color: "text-red-400" },
            { label: "High", value: stats?.high ?? 0, icon: AlertTriangle, color: "text-orange-400" },
            { label: "Medium", value: stats?.medium ?? 0, icon: AlertTriangle, color: "text-yellow-400" },
            { label: "Low", value: stats?.low ?? 0, icon: AlertTriangle, color: "text-primary" },
          ].map(s => (
            <div key={s.label} className="border border-border rounded-lg p-3 bg-card text-center">
              <div className={cn("text-2xl font-bold font-mono", s.color)}>{s.value}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <Tabs defaultValue="scans">
          <TabsList className="mb-4">
            <TabsTrigger value="scans" data-testid="tab-scans">Scans ({scans?.length ?? 0})</TabsTrigger>
            <TabsTrigger value="findings" data-testid="tab-findings">Findings ({findings?.length ?? 0})</TabsTrigger>
            <TabsTrigger value="evidence" data-testid="tab-evidence">Evidence ({evidence?.length ?? 0})</TabsTrigger>
          </TabsList>

          {/* Scans */}
          <TabsContent value="scans">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Scan History</h3>
              <Button size="sm" onClick={() => setShowScanForm(true)} className="gap-1.5" data-testid="button-new-scan">
                <Plus className="h-3.5 w-3.5" /> New Scan
              </Button>
            </div>
            {scans?.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-border rounded-lg text-muted-foreground text-sm">
                No scans yet. Start your first scan.
              </div>
            ) : (
              <div className="space-y-2">
                {scans?.map(scan => (
                  <div key={scan.id} className="flex items-center gap-4 border border-border rounded-lg px-4 py-3 bg-card" data-testid={`row-scan-${scan.id}`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate">{scan.name}</span>
                        <Badge variant="outline" className="text-xs font-mono">{scan.tool}</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground font-mono mt-0.5">{scan.target}</div>
                    </div>
                    <Badge variant="outline" className={cn("text-xs", SCAN_STATUS_COLORS[scan.status])}>
                      {scan.status}
                    </Badge>
                    <div className="flex gap-1">
                      {scan.status === "running" && (
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => {
                          stopScan.mutate({ params: { workspaceId: id!, scanId: scan.id } }, {
                            onSuccess: () => queryClient.invalidateQueries({ queryKey: getListScansQueryKey(id!) })
                          });
                        }} data-testid={`button-stop-scan-${scan.id}`}>
                          <Square className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => setDeleteScanId(scan.id)} data-testid={`button-delete-scan-${scan.id}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Findings */}
          <TabsContent value="findings">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Findings</h3>
              <Button size="sm" onClick={() => setShowFindingForm(true)} className="gap-1.5" data-testid="button-new-finding">
                <Plus className="h-3.5 w-3.5" /> Add Finding
              </Button>
            </div>
            {findings?.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-border rounded-lg text-muted-foreground text-sm">
                No findings yet. Add your first finding.
              </div>
            ) : (
              <div className="space-y-2">
                {findings?.map(f => (
                  <div key={f.id} className="flex items-start gap-4 border border-border rounded-lg px-4 py-3 bg-card" data-testid={`row-finding-${f.id}`}>
                    <Badge variant="outline" className={cn("text-xs capitalize flex-shrink-0 mt-0.5", SEV_COLORS[f.severity])}>
                      {f.severity}
                    </Badge>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{f.title}</div>
                      {f.affectedComponent && <div className="text-xs text-muted-foreground font-mono mt-0.5">{f.affectedComponent}</div>}
                    </div>
                    <Badge variant="outline" className="text-xs capitalize flex-shrink-0">{f.status}</Badge>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive flex-shrink-0" onClick={() => setDeleteFindingId(f.id)} data-testid={`button-delete-finding-${f.id}`}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Evidence */}
          <TabsContent value="evidence">
            {evidence?.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-border rounded-lg text-muted-foreground text-sm">
                No evidence collected yet.
              </div>
            ) : (
              <div className="space-y-2">
                {evidence?.map(e => (
                  <div key={e.id} className="flex items-center gap-4 border border-border rounded-lg px-4 py-3 bg-card" data-testid={`row-evidence-${e.id}`}>
                    <Database className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{e.name}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{e.type} — {format(new Date(e.createdAt), "MMM d, yyyy")}</div>
                    </div>
                    {e.hash && <span className="text-xs font-mono text-muted-foreground hidden md:block">{e.hash.slice(0, 12)}...</span>}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      {/* New Scan Dialog */}
      <Dialog open={showScanForm} onOpenChange={setShowScanForm}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Scan</DialogTitle></DialogHeader>
          <Form {...scanForm}>
            <form onSubmit={scanForm.handleSubmit(onCreateScan)} className="space-y-4">
              <FormField control={scanForm.control} name="name" render={({ field }) => (
                <FormItem><FormLabel>Scan Name</FormLabel><FormControl><Input placeholder="e.g. Initial Port Scan" {...field} data-testid="input-scan-name" /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={scanForm.control} name="target" render={({ field }) => (
                <FormItem><FormLabel>Target</FormLabel><FormControl><Input placeholder="e.g. 192.168.1.1 or example.com" {...field} data-testid="input-scan-target" /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={scanForm.control} name="tool" render={({ field }) => (
                <FormItem><FormLabel>Tool</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-scan-tool"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {TOOLS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowScanForm(false)}>Cancel</Button>
                <Button type="submit" className="flex-1" disabled={createScan.isPending} data-testid="button-submit-scan">
                  {createScan.isPending ? "Creating..." : "Create Scan"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* New Finding Dialog */}
      <Dialog open={showFindingForm} onOpenChange={setShowFindingForm}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Finding</DialogTitle></DialogHeader>
          <Form {...findingForm}>
            <form onSubmit={findingForm.handleSubmit(onCreateFinding)} className="space-y-4">
              <FormField control={findingForm.control} name="title" render={({ field }) => (
                <FormItem><FormLabel>Title</FormLabel><FormControl><Input placeholder="e.g. SQL Injection in Login Form" {...field} data-testid="input-finding-title" /></FormControl><FormMessage /></FormItem>
              )} />
              <FormField control={findingForm.control} name="severity" render={({ field }) => (
                <FormItem><FormLabel>Severity</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-finding-severity"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {["critical","high","medium","low","info"].map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <FormField control={findingForm.control} name="affectedComponent" render={({ field }) => (
                <FormItem><FormLabel>Affected Component</FormLabel><FormControl><Input placeholder="e.g. /api/login endpoint" {...field} data-testid="input-finding-component" /></FormControl></FormItem>
              )} />
              <FormField control={findingForm.control} name="description" render={({ field }) => (
                <FormItem><FormLabel>Description</FormLabel><FormControl><Textarea placeholder="Describe the vulnerability..." rows={3} {...field} data-testid="input-finding-description" /></FormControl></FormItem>
              )} />
              <FormField control={findingForm.control} name="recommendation" render={({ field }) => (
                <FormItem><FormLabel>Recommendation</FormLabel><FormControl><Textarea placeholder="How to fix..." rows={2} {...field} data-testid="input-finding-recommendation" /></FormControl></FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowFindingForm(false)}>Cancel</Button>
                <Button type="submit" className="flex-1" disabled={createFinding.isPending} data-testid="button-submit-finding">
                  {createFinding.isPending ? "Saving..." : "Add Finding"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmations */}
      <AlertDialog open={!!deleteScanId} onOpenChange={open => !open && setDeleteScanId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Scan?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete this scan and its data.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteScanId) return;
              deleteScan.mutate({ params: { workspaceId: id!, scanId: deleteScanId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListScansQueryKey(id!) }); setDeleteScanId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!deleteFindingId} onOpenChange={open => !open && setDeleteFindingId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Finding?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete this finding.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteFindingId) return;
              deleteFinding.mutate({ params: { workspaceId: id!, findingId: deleteFindingId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListFindingsQueryKey(id!) }); setDeleteFindingId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Layout>
  );
}
