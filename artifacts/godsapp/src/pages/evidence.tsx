import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useListWorkspaces, useListEvidence, useGetEvidenceCustody, useCreateEvidence, useDeleteEvidence, getListEvidenceQueryKey, getGetEvidenceCustodyQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Database, Plus, Trash2, ChevronRight, Hash, Clock } from "lucide-react";
import { format } from "date-fns";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const createSchema = z.object({
  workspaceId: z.string().min(1, "Workspace required"),
  name: z.string().min(1, "Name required"),
  type: z.string().default("text"),
  description: z.string().optional(),
  content: z.string().optional(),
});

type CreateForm = z.infer<typeof createSchema>;

function CustodyView({ workspaceId, evidenceId }: { workspaceId: string; evidenceId: string }) {
  const { data: custody, isLoading } = useGetEvidenceCustody(workspaceId, evidenceId, {
    query: { enabled: !!workspaceId && !!evidenceId, queryKey: getGetEvidenceCustodyQueryKey(workspaceId, evidenceId) }
  });

  if (isLoading) return <div className="space-y-2">{Array.from({length:3}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>;

  return (
    <div className="space-y-2">
      {custody?.map((entry, i) => (
        <div key={i} className="flex items-start gap-3 border border-border rounded-lg p-3 bg-card">
          <div className="h-2 w-2 rounded-full bg-primary mt-2 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm capitalize">{entry.action}</span>
              <span className="text-xs text-muted-foreground">by {entry.actor}</span>
            </div>
            {entry.notes && <p className="text-xs text-muted-foreground mt-0.5">{entry.notes}</p>}
            <p className="text-xs text-muted-foreground mt-0.5 font-mono">
              {format(new Date(entry.timestamp), "MMM d, yyyy HH:mm:ss")}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function WorkspaceEvidence({ workspaceId, workspaceName, onNew }: {
  workspaceId: string; workspaceName: string; onNew: () => void;
}) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { data: evidence, isLoading } = useListEvidence(workspaceId, { query: { enabled: !!workspaceId, queryKey: getListEvidenceQueryKey(workspaceId) } });
  const deleteEvidence = useDeleteEvidence();

  if (isLoading) return <div className="space-y-2 mb-4">{Array.from({length:2}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>;
  if (!evidence?.length) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
          {workspaceName} <Badge variant="outline" className="text-xs">{evidence.length}</Badge>
        </h3>
      </div>
      <div className="space-y-1.5">
        {evidence.map(e => (
          <div key={e.id} className="flex items-center gap-3 border border-border rounded-lg px-4 py-2.5 bg-card hover:bg-accent/30 transition-colors cursor-pointer group" onClick={() => setSelectedId(e.id)} data-testid={`row-evidence-${e.id}`}>
            <Database className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="font-medium text-sm">{e.name}</span>
            </div>
            <Badge variant="outline" className="text-xs capitalize">{e.type}</Badge>
            {e.hash && <div className="hidden md:flex items-center gap-1 text-xs text-muted-foreground"><Hash className="h-3 w-3" />{e.hash.slice(0,8)}...</div>}
            <span className="text-xs text-muted-foreground hidden lg:block">{format(new Date(e.createdAt), "MMM d")}</span>
            <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive" onClick={e2 => { e2.stopPropagation(); setDeleteId(e.id); }} data-testid={`button-delete-evidence-${e.id}`}>
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
      </div>

      <Sheet open={!!selectedId} onOpenChange={open => !open && setSelectedId(null)}>
        <SheetContent className="w-full sm:max-w-lg">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Chain of Custody
            </SheetTitle>
          </SheetHeader>
          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span>Full audit trail for this evidence item</span>
            </div>
            {selectedId && <CustodyView workspaceId={workspaceId} evidenceId={selectedId} />}
          </div>
        </SheetContent>
      </Sheet>

      <AlertDialog open={!!deleteId} onOpenChange={open => !open && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Evidence?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete the evidence and its chain of custody record.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive hover:bg-destructive/90" onClick={() => {
              if (!deleteId) return;
              deleteEvidence.mutate({ params: { workspaceId, evidenceId: deleteId } }, {
                onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListEvidenceQueryKey(workspaceId) }); setDeleteId(null); }
              });
            }}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Evidence() {
  const [showCreate, setShowCreate] = useState(false);
  const queryClient = useQueryClient();
  const { data: workspaces, isLoading } = useListWorkspaces();
  const createEvidence = useCreateEvidence();

  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { workspaceId: "", name: "", type: "text", description: "", content: "" },
  });

  const onSubmit = (data: CreateForm) => {
    const { workspaceId, ...rest } = data;
    createEvidence.mutate({ params: { workspaceId }, data: rest }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListEvidenceQueryKey(data.workspaceId) });
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
            <Database className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-2xl font-bold">Evidence Locker</h1>
              <p className="text-sm text-muted-foreground">Chain of custody tracking for all evidence</p>
            </div>
          </div>
          <Button onClick={() => setShowCreate(true)} className="gap-2" data-testid="button-add-evidence">
            <Plus className="h-4 w-4" /> Add Evidence
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:4}).map((_,i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !workspaces?.length ? (
          <div className="text-center py-20 text-muted-foreground">Create a workspace first to start collecting evidence.</div>
        ) : (
          workspaces.map(ws => <WorkspaceEvidence key={ws.id} workspaceId={ws.id} workspaceName={ws.name} onNew={() => setShowCreate(true)} />)
        )}
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Evidence</DialogTitle></DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="workspaceId" render={({ field }) => (
                <FormItem><FormLabel>Workspace</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-evidence-workspace"><SelectValue placeholder="Select workspace" /></SelectTrigger></FormControl>
                    <SelectContent>
                      {workspaces?.map(ws => <SelectItem key={ws.id} value={ws.id}>{ws.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <FormField control={form.control} name="name" render={({ field }) => (
                <FormItem><FormLabel>Name</FormLabel><FormControl><Input placeholder="Evidence item name" {...field} data-testid="input-evidence-name" /></FormControl></FormItem>
              )} />
              <FormField control={form.control} name="type" render={({ field }) => (
                <FormItem><FormLabel>Type</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl><SelectTrigger data-testid="select-evidence-type"><SelectValue /></SelectTrigger></FormControl>
                    <SelectContent>
                      {["text","screenshot","file","network-capture","command-output"].map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </FormItem>
              )} />
              <FormField control={form.control} name="content" render={({ field }) => (
                <FormItem><FormLabel>Content</FormLabel><FormControl><Textarea placeholder="Evidence content or notes" rows={4} {...field} data-testid="input-evidence-content" /></FormControl></FormItem>
              )} />
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button type="submit" className="flex-1" disabled={createEvidence.isPending} data-testid="button-submit-evidence">
                  {createEvidence.isPending ? "Saving..." : "Add Evidence"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </Layout>
  );
}
