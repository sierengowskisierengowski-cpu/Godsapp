import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useListWorkspaces, useListSchedules, useCreateSchedule, useDeleteSchedule, getListSchedulesQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Calendar, Plus, Trash2, Clock } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at midnight", value: "0 0 * * *" },
  { label: "Weekly (Monday)", value: "0 0 * * 1" },
  { label: "Monthly (1st)", value: "0 0 1 * *" },
];

const createSchema = z.object({
  workspaceId: z.string().min(1, "Workspace required"),
  name: z.string().min(1, "Name required"),
  cron: z.string().min(1, "Schedule required"),
  tool: z.string().default("nmap"),
  target: z.string().min(1, "Target required"),
});

type CreateForm = z.infer<typeof createSchema>;

function WorkspaceSchedules({ workspaceId, workspaceName }: { workspaceId: string; workspaceName: string }) {
  const queryClient = useQueryClient();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { data: schedules, isLoading } = useListSchedules(workspaceId, { query: { enabled: !!workspaceId, queryKey: getListSchedulesQueryKey(workspaceId) } });
  const deleteSchedule = useDeleteSchedule();

  if (isLoading) return <div className="space-y-2 mb-4">{Array.from({length:2}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>;
  if (!schedules?.length) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-2">
        {workspaceName} <Badge variant="outline" className="text-xs">{schedules.length}</Badge>
      </h3>
      <div className="space-y-1.5">
        {schedules.map(s => (
          <div key={s.id} className="flex items-center gap-4 border border-border rounded-lg px-4 py-3 bg-card group" data-testid={`row-schedule-${s.id}`}>
            <div className={cn("h-2 w-2 rounded-full flex-shrink-0", s.enabled ? "bg-primary" : "bg-muted-foreground")} />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm">{s.name}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs font-mono text-muted-foreground">{s.cron}</span>
                {s.nextRunAt && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    Next: {format(new Date(s.nextRunAt), "MMM d, HH:mm")}
                  </div>
                )}
              </div>
            </div>
            <Badge variant="outline" className="text-xs">{s.enabled ? "Active" : "Paused"}</Badge>
            <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive" onClick={() => setDeleteId(s.id)} data-testid={`button-delete-schedule-${s.id}`}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
      </div>

      <AlertDialog open={!!deleteId} onOpenChange={open => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Schedule?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete this scheduled scan.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteId) return;
              deleteSchedule.mutate({ params: { workspaceId, scheduleId: deleteId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListSchedulesQueryKey(workspaceId) }); setDeleteId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Scheduler() {
  const [showCreate, setShowCreate] = useState(false);
  const [customCron, setCustomCron] = useState(false);
  const queryClient = useQueryClient();
  const { data: workspaces, isLoading } = useListWorkspaces();
  const createSchedule = useCreateSchedule();

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { workspaceId: "", name: "", cron: "0 0 * * *", tool: "nmap", target: "" },
  });

  const onSubmit = (data: CreateForm) => {
    const { workspaceId, tool, target, ...rest } = data;
    createSchedule.mutate({ params: { workspaceId }, data: { ...rest, scanConfig: JSON.stringify({ tool, target }) } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListSchedulesQueryKey(workspaceId) });
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
            <Calendar className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-2xl font-bold">Scheduler</h1>
              <p className="text-sm text-muted-foreground">Automate recurring scans with cron schedules</p>
            </div>
          </div>
          <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="button-create-schedule">
            <Plus className="h-4 w-4" /> New Schedule
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:3}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !workspaces?.length ? (
          <div className="text-center py-20 text-muted-foreground">Create a workspace to start scheduling scans.</div>
        ) : (
          workspaces.map(ws => <WorkspaceSchedules key={ws.id} workspaceId={ws.id} workspaceName={ws.name} />)
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Schedule</DialogTitle></DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="workspaceId" render={({ field }) => (
                <FormItem><FormLabel>Workspace</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-schedule-workspace"><SelectValue placeholder="Select workspace" /></SelectTrigger></FormControl>
                    <SelectContent>
                      {workspaces?.map(ws => <SelectItem key={ws.id} value={ws.id}>{ws.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem><FormLabel>Schedule Name</FormLabel><FormControl><Input placeholder="e.g. Daily Port Scan" {...field} data-testid="input-schedule-name" /></FormControl><FormMessage /></FormItem>
              )} />
              <div className="grid grid-cols-2 gap-4">
                <FormField control={form.control} name="tool" render={({ field }) => (
                  <FormItem><FormLabel>Tool</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        {["nmap","gobuster","nikto","sqlmap","custom"].map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )} />
                <FormField control={form.control} name="target" render={({ field }) => (
                  <FormItem><FormLabel>Target</FormLabel><FormControl><Input placeholder="e.g. 192.168.1.1" {...field} data-testid="input-schedule-target" /></FormControl><FormMessage /></FormItem>
                )} />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <FormLabel>Schedule</FormLabel>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>Custom cron</span>
                    <Switch checked={customCron} onCheckedChange={setCustomCron} data-testid="switch-custom-cron" />
                  </div>
                </div>
                {customCron ? (
                  <FormField control={form.control} name="cron" render={({ field }) => (
                    <FormItem><FormControl><Input placeholder="* * * * *" {...field} className="font-mono" data-testid="input-cron-expression" /></FormControl><FormMessage /></FormItem>
                  )} />
                ) : (
                  <FormField control={form.control} name="cron" render={({ field }) => (
                    <FormItem>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger data-testid="select-cron-preset"><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          {CRON_PRESETS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />
                )}
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button type="submit" className="flex-1" disabled={createSchedule.isPending} data-testid="button-submit-schedule">
                  {createSchedule.isPending ? "Creating..." : "Create Schedule"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
