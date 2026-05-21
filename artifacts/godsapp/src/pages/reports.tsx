import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useListWorkspaces, useListReports, useGenerateReport, useDeleteReport, useGetReport, getListReportsQueryKey, getGetReportQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { FileText, Plus, Trash2, Eye, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  generating: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  completed: "bg-green-500/15 text-green-400 border-green-500/30",
  failed: "bg-red-500/15 text-red-400 border-red-500/30",
};

const createSchema = z.object({
  workspaceId: z.string().min(1, "Workspace required"),
  title: z.string().optional(),
  type: z.string().default("markdown"),
});

type CreateForm = z.infer<typeof createSchema>;

function ReportViewer({ workspaceId, reportId, onClose }: { workspaceId: string; reportId: string; onClose: () => void }) {
  const { data: report, isLoading } = useGetReport(workspaceId, reportId, {
    query: { enabled: !!workspaceId && !!reportId, queryKey: getGetReportQueryKey(workspaceId, reportId) }
  });
  return (
    <Sheet open={!!reportId} onOpenChange={open => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            {report?.title ?? "Report"}
          </SheetTitle>
        </SheetHeader>
        <ScrollArea className="mt-4 h-[calc(100vh-8rem)]">
          {isLoading ? (
            <div className="space-y-2">{Array.from({length:5}).map((_,i) => <Skeleton key={i} className="h-4" />)}</div>
          ) : (
            <pre className="terminal-text text-xs whitespace-pre-wrap text-foreground/90 leading-relaxed">
              {report?.content ?? "No content available"}
            </pre>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

function WorkspaceReports({ workspaceId, workspaceName }: { workspaceId: string; workspaceName: string }) {
  const queryClient = useQueryClient();
  const [viewId, setViewId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { data: reports, isLoading } = useListReports(workspaceId, { query: { enabled: !!workspaceId, queryKey: getListReportsQueryKey(workspaceId) } });
  const deleteReport = useDeleteReport();

  if (isLoading) return <div className="space-y-2 mb-4">{Array.from({length:2}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>;
  if (!reports?.length) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
        {workspaceName} <Badge variant="outline" className="text-xs">{reports.length}</Badge>
      </h3>
      <div className="space-y-1.5">
        {reports.map(r => (
          <div key={r.id} className="flex items-center gap-3 border border-border rounded-lg px-4 py-2.5 bg-card group" data-testid={`row-report-${r.id}`}>
            <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="font-medium text-sm truncate block">{r.title}</span>
              {r.generatedAt && <span className="text-xs text-muted-foreground">{format(new Date(r.generatedAt), "MMM d, yyyy HH:mm")}</span>}
            </div>
            <Badge variant="outline" className={cn("text-xs capitalize", STATUS_COLORS[r.status])}>{r.status}</Badge>
            <Badge variant="outline" className="text-xs uppercase">{r.type}</Badge>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100">
              {r.status === "completed" && (
                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary" onClick={() => setViewId(r.id)} data-testid={`button-view-report-${r.id}`}>
                  <Eye className="h-3.5 w-3.5" />
                </Button>
              )}
              <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => setDeleteId(r.id)} data-testid={`button-delete-report-${r.id}`}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
      </div>

      {viewId && <ReportViewer workspaceId={workspaceId} reportId={viewId} onClose={() => setViewId(null)} />}

      <AlertDialog open={!!deleteId} onOpenChange={open => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Report?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete the report.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteId) return;
              deleteReport.mutate({ params: { workspaceId, reportId: deleteId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListReportsQueryKey(workspaceId) }); setDeleteId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Reports() {
  const [showCreate, setShowCreate] = useState(false);
  const queryClient = useQueryClient();
  const { data: workspaces, isLoading } = useListWorkspaces();
  const generateReport = useGenerateReport();

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { workspaceId: "", title: "", type: "markdown" },
  });

  const onSubmit = (data: CreateForm) => {
    const { workspaceId, ...rest } = data;
    generateReport.mutate({ params: { workspaceId }, data: rest }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListReportsQueryKey(workspaceId) });
        setShowCreate(false);
        form.reset();
      }
    });
  };

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <FileText className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-2xl font-bold">Reports</h1>
              <p className="text-sm text-muted-foreground">Generate and manage security assessment reports</p>
            </div>
          </div>
          <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="button-generate-report">
            <Plus className="h-4 w-4" /> Generate Report
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:3}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !workspaces?.length ? (
          <div className="text-center py-20 text-muted-foreground">Create a workspace to generate reports.</div>
        ) : (
          workspaces.map(ws => <WorkspaceReports key={ws.id} workspaceId={ws.id} workspaceName={ws.name} />)
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle>Generate Report</DialogTitle></DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="workspaceId" render={({ field }) => (
                <FormItem><FormLabel>Workspace</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-report-workspace"><SelectValue placeholder="Select workspace" /></SelectTrigger></FormControl>
                    <SelectContent>
                      {workspaces?.map(ws => <SelectItem key={ws.id} value={ws.id}>{ws.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <FormField control={form.control} name="title" render={({ field }) => (
                <FormItem><FormLabel>Report Title <span className="text-muted-foreground">(optional)</span></FormLabel>
                  <FormControl><Input placeholder="Auto-generated if left blank" {...field} data-testid="input-report-title" /></FormControl>
                </FormItem>
              )} />
              <FormField control={form.control} name="type" render={({ field }) => (
                <FormItem><FormLabel>Format</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-report-type"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {["markdown","html","json"].map(t => <SelectItem key={t} value={t}>{t.toUpperCase()}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button type="submit" className="flex-1 gap-2" disabled={generateReport.isPending} data-testid="button-submit-report">
                  {generateReport.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</> : "Generate Report"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
