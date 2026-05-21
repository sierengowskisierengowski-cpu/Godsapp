import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  useGetGeneralSettings, useUpdateGeneralSettings, useGetApiKeys, useUpsertApiKey, useTestApiKey,
  useGetAuditLog, useChangePassword,
  getGetGeneralSettingsQueryKey, getGetApiKeysQueryKey, getGetAuditLogQueryKey
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Settings, Key, Shield, FileText, Lock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

const generalSchema = z.object({
  operatorName: z.string().min(1, "Name required"),
  organization: z.string().optional(),
  autoLockMinutes: z.string().default("30"),
});

const passwordSchema = z.object({
  currentPassword: z.string().min(1),
  newPassword: z.string().min(14, "Minimum 14 characters"),
  confirm: z.string(),
}).refine(d => d.newPassword === d.confirm, { message: "Passwords do not match", path: ["confirm"] });

type GeneralForm = z.infer<typeof generalSchema>;
type PasswordForm = z.infer<typeof passwordSchema>;

const API_KEY_SERVICES = [
  { id: "hibp", name: "HaveIBeenPwned", description: "Breach checking" },
  { id: "shodan", name: "Shodan", description: "IoT/device search" },
  { id: "virustotal", name: "VirusTotal", description: "Malware analysis" },
  { id: "ipstack", name: "IPStack", description: "IP geolocation" },
  { id: "censys", name: "Censys", description: "Internet-wide scan data" },
];

function ApiKeyRow({ service, name, description }: { service: string; name: string; description: string }) {
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: keys, isLoading } = useGetApiKeys({ query: { queryKey: getGetApiKeysQueryKey() } });
  const upsertKey = useUpsertApiKey();
  const testKey = useTestApiKey();

  const existing = keys?.find(k => k.service === service);

  const save = () => {
    if (!key.trim()) return;
    upsertKey.mutate({ params: { service }, data: { key } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetApiKeysQueryKey() });
        setEditing(false);
        setKey("");
        toast({ title: "API key saved" });
      }
    });
  };

  const test = () => {
    testKey.mutate({ params: { service } }, {
      onSuccess: () => toast({ title: "API key is valid" }),
      onError: () => toast({ title: "API key test failed", variant: "destructive" }),
    });
  };

  return (
    <div className="border border-border rounded-lg p-4 bg-card space-y-3" data-testid={`row-apikey-${service}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{name}</span>
            {existing ? (
              <Badge variant="outline" className="text-xs text-green-400 border-green-500/20 bg-green-500/10 gap-1">
                <CheckCircle className="h-3 w-3" /> Configured
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs text-muted-foreground gap-1">
                <XCircle className="h-3 w-3" /> Not set
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        </div>
        <div className="flex gap-2">
          {existing && (
            <Button variant="outline" size="sm" onClick={test} disabled={testKey.isPending} className="h-7 text-xs" data-testid={`button-test-apikey-${service}`}>
              {testKey.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Test"}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setEditing(!editing)} className="h-7 text-xs" data-testid={`button-edit-apikey-${service}`}>
            {editing ? "Cancel" : existing ? "Update" : "Add"}
          </Button>
        </div>
      </div>
      {existing && !editing && (
        <div className="font-mono text-xs text-muted-foreground">{existing.key}</div>
      )}
      {editing && (
        <div className="flex gap-2">
          <Input
            type="password"
            placeholder="Paste API key"
            value={key}
            onChange={e => setKey(e.target.value)}
            className="font-mono text-sm"
            data-testid={`input-apikey-${service}`}
          />
          <Button size="sm" onClick={save} disabled={upsertKey.isPending} data-testid={`button-save-apikey-${service}`}>
            {upsertKey.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
          </Button>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: generalSettings, isLoading: gsLoading } = useGetGeneralSettings({ query: { queryKey: getGetGeneralSettingsQueryKey() } });
  const { data: auditLog } = useGetAuditLog(undefined, { query: { queryKey: getGetAuditLogQueryKey() } });
  const updateGeneral = useUpdateGeneralSettings();
  const changePassword = useChangePassword();

  const generalForm = useForm<GeneralForm>({
    resolver: zodResolver(generalSchema),
    values: {
      operatorName: generalSettings?.operatorName ?? "",
      organization: generalSettings?.organization ?? "",
      autoLockMinutes: generalSettings?.autoLockMinutes ?? "30",
    },
  });

  const passwordForm = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirm: "" },
  });

  const onSaveGeneral = (data: GeneralForm) => {
    updateGeneral.mutate({ data }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetGeneralSettingsQueryKey() });
        toast({ title: "Settings saved" });
      }
    });
  };

  const onChangePassword = (data: PasswordForm) => {
    changePassword.mutate({ data: { currentPassword: data.currentPassword, newPassword: data.newPassword } }, {
      onSuccess: () => {
        toast({ title: "Password changed successfully" });
        passwordForm.reset();
      },
      onError: () => toast({ title: "Password change failed", variant: "destructive" })
    });
  };

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Settings className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-sm text-muted-foreground">Operator profile, API keys, security</p>
          </div>
        </div>

        <Tabs defaultValue="general">
          <TabsList className="mb-6">
            <TabsTrigger value="general" data-testid="tab-general"><Settings className="h-3.5 w-3.5 mr-1.5" />General</TabsTrigger>
            <TabsTrigger value="apikeys" data-testid="tab-apikeys"><Key className="h-3.5 w-3.5 mr-1.5" />API Keys</TabsTrigger>
            <TabsTrigger value="security" data-testid="tab-security"><Lock className="h-3.5 w-3.5 mr-1.5" />Security</TabsTrigger>
            <TabsTrigger value="audit" data-testid="tab-audit"><FileText className="h-3.5 w-3.5 mr-1.5" />Audit Log</TabsTrigger>
          </TabsList>

          {/* General */}
          <TabsContent value="general">
            {gsLoading ? (
              <div className="space-y-3">{Array.from({length:3}).map((_,i) => <Skeleton key={i} className="h-10" />)}</div>
            ) : (
              <Form {...generalForm}>
                <form onSubmit={generalForm.handleSubmit(onSaveGeneral)} className="space-y-4 max-w-md">
                  <FormField control={generalForm.control} name="operatorName" render={({ field }) => (
                    <FormItem><FormLabel>Operator Name</FormLabel><FormControl><Input {...field} data-testid="input-operator-name" /></FormControl><FormMessage /></FormItem>
                  )} />
                  <FormField control={generalForm.control} name="organization" render={({ field }) => (
                    <FormItem><FormLabel>Organization</FormLabel><FormControl><Input {...field} data-testid="input-organization" /></FormControl></FormItem>
                  )} />
                  <FormField control={generalForm.control} name="autoLockMinutes" render={({ field }) => (
                    <FormItem><FormLabel>Auto-lock after (minutes)</FormLabel><FormControl><Input type="number" {...field} data-testid="input-auto-lock" /></FormControl></FormItem>
                  )} />
                  <Button type="submit" disabled={updateGeneral.isPending} data-testid="button-save-general">
                    {updateGeneral.isPending ? "Saving..." : "Save Changes"}
                  </Button>
                </form>
              </Form>
            )}
          </TabsContent>

          {/* API Keys */}
          <TabsContent value="apikeys" className="space-y-3">
            <p className="text-sm text-muted-foreground mb-4">
              Configure API keys for external intelligence services. Keys are stored encrypted.
            </p>
            {API_KEY_SERVICES.map(s => (
              <ApiKeyRow key={s.id} service={s.id} name={s.name} description={s.description} />
            ))}
          </TabsContent>

          {/* Security */}
          <TabsContent value="security">
            <div className="max-w-md space-y-6">
              <div className="border border-border rounded-lg p-4 bg-card">
                <h3 className="font-semibold mb-1 flex items-center gap-2">
                  <Lock className="h-4 w-4 text-primary" />
                  Change Master Password
                </h3>
                <p className="text-xs text-muted-foreground mb-4">New password must be at least 14 characters.</p>
                <Form {...passwordForm}>
                  <form onSubmit={passwordForm.handleSubmit(onChangePassword)} className="space-y-3">
                    <FormField control={passwordForm.control} name="currentPassword" render={({ field }) => (
                      <FormItem><FormLabel>Current Password</FormLabel><FormControl><Input type="password" {...field} data-testid="input-current-password" /></FormControl><FormMessage /></FormItem>
                    )} />
                    <FormField control={passwordForm.control} name="newPassword" render={({ field }) => (
                      <FormItem><FormLabel>New Password</FormLabel><FormControl><Input type="password" {...field} data-testid="input-new-password" /></FormControl><FormMessage /></FormItem>
                    )} />
                    <FormField control={passwordForm.control} name="confirm" render={({ field }) => (
                      <FormItem><FormLabel>Confirm New Password</FormLabel><FormControl><Input type="password" {...field} data-testid="input-confirm-password" /></FormControl><FormMessage /></FormItem>
                    )} />
                    <Button type="submit" disabled={changePassword.isPending} data-testid="button-change-password">
                      {changePassword.isPending ? "Changing..." : "Change Password"}
                    </Button>
                  </form>
                </Form>
              </div>
            </div>
          </TabsContent>

          {/* Audit Log */}
          <TabsContent value="audit">
            <div className="border border-border rounded-lg overflow-hidden">
              <div className="px-4 py-2 bg-muted/30 border-b border-border flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Audit Log</span>
                <span className="text-xs text-muted-foreground">{auditLog?.length ?? 0} entries</span>
              </div>
              <ScrollArea className="h-96">
                {auditLog?.map((entry, i) => (
                  <div key={i} className="flex items-start gap-4 px-4 py-2.5 border-b border-border/50 hover:bg-accent/20" data-testid={`row-audit-${i}`}>
                    <span className="text-xs font-mono text-muted-foreground flex-shrink-0 mt-0.5">
                      {format(new Date(entry.timestamp), "MMM d HH:mm:ss")}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-medium font-mono text-primary">{entry.action}</span>
                      {entry.resource && (
                        <span className="text-xs text-muted-foreground ml-2">{entry.resource}</span>
                      )}
                      {entry.detail && (
                        <p className="text-xs text-muted-foreground truncate">{entry.detail}</p>
                      )}
                    </div>
                    {entry.ip && (
                      <span className="text-xs font-mono text-muted-foreground flex-shrink-0">{entry.ip}</span>
                    )}
                  </div>
                ))}
              </ScrollArea>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
