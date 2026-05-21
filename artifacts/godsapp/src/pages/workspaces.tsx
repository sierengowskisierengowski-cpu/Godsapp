import { useState } from "react";
import { useLocation } from "wouter";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useListWorkspaces, useCreateWorkspace, useDeleteWorkspace, getListWorkspacesQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Plus, FolderOpen, Trash2, ChevronRight, Target, Calendar } from "lucide-react";
import { StatusDot } from "@/components/status-border";
import { MatrixText } from "@/components/matrix-text";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

const schema = z.object({
  name: z.string().min(1, "Name required"),
  description: z.string().optional(),
  target: z.string().optional(),
  type: z.string().default("pentest"),
});

type FormData = z.infer<typeof schema>;

const TYPE_COLORS: Record<string, string> = {
  pentest: "bg-primary/10 text-primary border-primary/20",
  "bug-bounty": "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  "red-team": "bg-red-500/10 text-red-500 border-red-500/20",
  audit: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/10 text-green-500 border-green-500/20",
  archived: "bg-muted text-muted-foreground border-border",
  completed: "bg-blue-500/10 text-blue-500 border-blue-500/20",
};

export default function Workspaces() {
  const [, setLocation] = useLocation();
  const [showCreate, setShowCreate] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: workspaces, isLoading } = useListWorkspaces({ query: { queryKey: getListWorkspacesQueryKey() } });
  const createWorkspace = useCreateWorkspace();
  const deleteWorkspace = useDeleteWorkspace();

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", target: "", type: "pentest" },
  });

  const onSubmit = (data: FormData) => {
    createWorkspace.mutate({ data }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListWorkspacesQueryKey() });
        setShowCreate(false);
        form.reset();
      }
    });
  };

  const onDelete = () => {
    if (!deleteId) return;
    deleteWorkspace.mutate({ params: { id: deleteId } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListWorkspacesQueryKey() });
        setDeleteId(null);
      }
    });
  };

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Workspaces</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Organize assessments by target or engagement</p>
          </div>
          <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="button-create-workspace">
            <Plus className="h-4 w-4" /> New Workspace
          </Button>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : workspaces?.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-border rounded-lg">
            <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <h3 className="font-semibold mb-1">No Workspaces</h3>
            <p className="text-sm text-muted-foreground mb-4">Create your first workspace to start an assessment</p>
            <Button onClick={() => setShowCreate(true)} variant="outline" className="gap-2">
              <Plus className="h-4 w-4" /> Create Workspace
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workspaces?.map(ws => (
              <div
                key={ws.id}
                className="border border-border/50 rounded-lg p-4 glass-card hover:border-primary/40 hover:shadow-[0_0_16px_rgba(34,211,238,0.08)] transition-all cursor-pointer group relative"
                onClick={() => setLocation(`/workspaces/${ws.id}`)}
                data-testid={`card-workspace-${ws.id}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <FolderOpen className="h-4 w-4 text-primary flex-shrink-0" />
                    <MatrixText text={ws.name} className="font-semibold truncate" duration={350} />
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive flex-shrink-0"
                    onClick={e => { e.stopPropagation(); setDeleteId(ws.id); }}
                    data-testid={`button-delete-workspace-${ws.id}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {ws.target && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3">
                    <Target className="h-3 w-3" />
                    <span className="font-mono truncate">{ws.target}</span>
                  </div>
                )}

                {ws.description && (
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{ws.description}</p>
                )}

                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className={cn("text-xs capitalize", TYPE_COLORS[ws.type] ?? "")}>
                    {ws.type}
                  </Badge>
                  <Badge variant="outline" className={cn("text-xs capitalize", STATUS_COLORS[ws.status] ?? "")}>
                    {ws.status}
                  </Badge>
                </div>

                <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/50">
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    {format(new Date(ws.createdAt), "MMM d, yyyy")}
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Workspace</DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl><Input placeholder="e.g. ACME Corp Pentest" {...field} data-testid="input-workspace-name" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <FormField control={form.control} name="target" render={({ field }) => (
                <FormItem>
                  <FormLabel>Target <span className="text-muted-foreground">(optional)</span></FormLabel>
                  <FormControl><Input placeholder="e.g. 192.168.1.0/24 or example.com" {...field} data-testid="input-workspace-target" /></FormControl>
                </FormItem>
              )} />
              <FormField control={form.control} name="type" render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger data-testid="select-workspace-type">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="pentest">Penetration Test</SelectItem>
                      <SelectItem value="bug-bounty">Bug Bounty</SelectItem>
                      <SelectItem value="red-team">Red Team</SelectItem>
                      <SelectItem value="audit">Security Audit</SelectItem>
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <FormField control={form.control} name="description" render={({ field }) => (
                <FormItem>
                  <FormLabel>Description <span className="text-muted-foreground">(optional)</span></FormLabel>
                  <FormControl><Input placeholder="Brief description of the engagement" {...field} data-testid="input-workspace-description" /></FormControl>
                </FormItem>
              )} />
              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button type="submit" className="flex-1" disabled={createWorkspace.isPending} data-testid="button-submit-workspace">
                  {createWorkspace.isPending ? "Creating..." : "Create Workspace"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={open => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Workspace?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the workspace and all associated scans, findings, and evidence. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onDelete} className="bg-destructive hover:bg-destructive/90" data-testid="button-confirm-delete">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Layout>
  );
}
