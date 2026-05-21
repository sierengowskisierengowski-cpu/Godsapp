import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLookupIpIntel, useCheckHibp } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Search, AlertTriangle, CheckCircle, Loader2, Shield, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

function ResultBox({ data, isLoading }: { data: unknown; isLoading: boolean }) {
  if (isLoading) return (
    <div className="flex items-center justify-center h-32 border border-border rounded-lg bg-card">
      <Loader2 className="h-5 w-5 animate-spin text-primary" />
    </div>
  );
  if (!data) return (
    <div className="flex items-center justify-center h-32 border border-dashed border-border rounded-lg text-muted-foreground text-sm">
      Results will appear here
    </div>
  );
  return (
    <ScrollArea className="h-80 border border-border rounded-lg bg-[hsl(222_28%_6%)] p-4">
      <pre className="terminal-text text-primary/90 whitespace-pre-wrap break-all">
        {JSON.stringify(data, null, 2)}
      </pre>
    </ScrollArea>
  );
}

const ipSchema = z.object({ ip: z.string().min(1) });
const hibpSchema = z.object({ email: z.string().email("Valid email required") });

export default function IntelTools() {
  const [ipResult, setIpResult] = useState<unknown>(null);
  const [hibpResult, setHibpResult] = useState<{ email: string; breaches: { Name: string; Domain: string; BreachDate: string }[]; pwned: boolean } | null>(null);

  const ipIntel = useLookupIpIntel();
  const checkHibp = useCheckHibp();

  const ipForm = useForm({ resolver: zodResolver(ipSchema), defaultValues: { ip: "" } });
  const hibpForm = useForm({ resolver: zodResolver(hibpSchema), defaultValues: { email: "" } });

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Search className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Threat Intelligence</h1>
            <p className="text-sm text-muted-foreground">IP intelligence, breach checking</p>
          </div>
        </div>

        <Tabs defaultValue="ip">
          <TabsList className="mb-6">
            <TabsTrigger value="ip" data-testid="tab-ip-intel">IP Intelligence</TabsTrigger>
            <TabsTrigger value="hibp" data-testid="tab-hibp">Breach Check (HIBP)</TabsTrigger>
          </TabsList>

          <TabsContent value="ip" className="space-y-4">
            <Form {...ipForm}>
              <form onSubmit={ipForm.handleSubmit(d => {
                ipIntel.mutate({ data: d }, { onSuccess: setIpResult });
              })} className="flex gap-2">
                <FormField control={ipForm.control} name="ip" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="IP address (e.g. 8.8.8.8)" {...field} data-testid="input-intel-ip" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={ipIntel.isPending} className="gap-2" data-testid="button-ip-intel">
                  {ipIntel.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cpu className="h-4 w-4" />}
                  Lookup
                </Button>
              </form>
            </Form>
            <ResultBox data={ipResult} isLoading={ipIntel.isPending} />
          </TabsContent>

          <TabsContent value="hibp" className="space-y-4">
            <div className="flex items-start gap-2 p-3 rounded-lg border border-border bg-muted/20 text-xs text-muted-foreground">
              <Shield className="h-4 w-4 flex-shrink-0 mt-0.5 text-primary" />
              <span>Requires a HaveIBeenPwned API key. Configure it in Settings &rarr; API Keys.</span>
            </div>
            <Form {...hibpForm}>
              <form onSubmit={hibpForm.handleSubmit(d => {
                checkHibp.mutate({ data: d }, { onSuccess: (r) => setHibpResult(r as typeof hibpResult) });
              })} className="flex gap-2">
                <FormField control={hibpForm.control} name="email" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Email address to check" type="email" {...field} data-testid="input-hibp-email" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={checkHibp.isPending} className="gap-2" data-testid="button-hibp-check">
                  {checkHibp.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Check
                </Button>
              </form>
            </Form>

            {hibpResult && (
              <div className="border border-border rounded-lg p-4 bg-card space-y-3">
                <div className={cn("flex items-center gap-2", hibpResult.pwned ? "text-red-400" : "text-green-400")}>
                  {hibpResult.pwned ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle className="h-5 w-5" />}
                  <span className="font-semibold">
                    {hibpResult.pwned
                      ? `${hibpResult.breaches.length} breach${hibpResult.breaches.length !== 1 ? "es" : ""} found`
                      : "No breaches found"}
                  </span>
                </div>
                {hibpResult.breaches?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {hibpResult.breaches.map((b, i) => (
                      <Badge key={i} variant="outline" className="text-xs border-red-500/20 text-red-400">
                        {b.Name} ({b.BreachDate})
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
