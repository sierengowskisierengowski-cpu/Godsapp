import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRunDnsLookup, useRunWhoisLookup, useLookupIpIntel } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Network, Globe, Cpu, Loader2, Search } from "lucide-react";
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

const dnsSchema = z.object({ target: z.string().min(1), type: z.string().default("A") });
const whoisSchema = z.object({ target: z.string().min(1) });
const ipSchema = z.object({ ip: z.string().min(1) });

export default function NetworkTools() {
  const [dnsResult, setDnsResult] = useState<unknown>(null);
  const [whoisResult, setWhoisResult] = useState<unknown>(null);
  const [ipResult, setIpResult] = useState<unknown>(null);

  const dnsLookup = useRunDnsLookup();
  const whoisLookup = useRunWhoisLookup();
  const ipIntel = useLookupIpIntel();

  const dnsForm = useForm({ resolver: zodResolver(dnsSchema), defaultValues: { target: "", type: "A" } });
  const whoisForm = useForm({ resolver: zodResolver(whoisSchema), defaultValues: { target: "" } });
  const ipForm = useForm({ resolver: zodResolver(ipSchema), defaultValues: { ip: "" } });

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Network className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Network Recon</h1>
            <p className="text-sm text-muted-foreground">DNS lookup, WHOIS, IP intelligence</p>
          </div>
        </div>

        <Tabs defaultValue="dns">
          <TabsList className="mb-6">
            <TabsTrigger value="dns" data-testid="tab-dns">DNS Lookup</TabsTrigger>
            <TabsTrigger value="whois" data-testid="tab-whois">WHOIS</TabsTrigger>
            <TabsTrigger value="ip" data-testid="tab-ip">IP Intelligence</TabsTrigger>
          </TabsList>

          <TabsContent value="dns" className="space-y-4">
            <Form {...dnsForm}>
              <form onSubmit={dnsForm.handleSubmit(d => {
                dnsLookup.mutate({ data: d }, { onSuccess: setDnsResult, onError: e => setDnsResult(e) });
              })} className="flex gap-2">
                <FormField control={dnsForm.control} name="target" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Domain (e.g. example.com)" {...field} data-testid="input-dns-target" /></FormControl>
                  </FormItem>
                )} />
                <FormField control={dnsForm.control} name="type" render={({ field }) => (
                  <FormItem className="w-28">
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl><SelectTrigger data-testid="select-dns-type"><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>
                        {["A","AAAA","MX","NS","TXT","CNAME","SOA"].map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )} />
                <Button type="submit" disabled={dnsLookup.isPending} className="gap-2" data-testid="button-dns-lookup">
                  {dnsLookup.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Lookup
                </Button>
              </form>
            </Form>
            <ResultBox data={dnsResult} isLoading={dnsLookup.isPending} />
          </TabsContent>

          <TabsContent value="whois" className="space-y-4">
            <Form {...whoisForm}>
              <form onSubmit={whoisForm.handleSubmit(d => {
                whoisLookup.mutate({ data: d }, { onSuccess: setWhoisResult });
              })} className="flex gap-2">
                <FormField control={whoisForm.control} name="target" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Domain or IP (e.g. example.com)" {...field} data-testid="input-whois-target" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={whoisLookup.isPending} className="gap-2" data-testid="button-whois-lookup">
                  {whoisLookup.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
                  Lookup
                </Button>
              </form>
            </Form>
            <ResultBox data={whoisResult} isLoading={whoisLookup.isPending} />
          </TabsContent>

          <TabsContent value="ip" className="space-y-4">
            <Form {...ipForm}>
              <form onSubmit={ipForm.handleSubmit(d => {
                ipIntel.mutate({ data: d }, { onSuccess: setIpResult });
              })} className="flex gap-2">
                <FormField control={ipForm.control} name="ip" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="IP address (e.g. 8.8.8.8)" {...field} data-testid="input-ip-address" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={ipIntel.isPending} className="gap-2" data-testid="button-ip-lookup">
                  {ipIntel.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Cpu className="h-4 w-4" />}
                  Analyze
                </Button>
              </form>
            </Form>
            <ResultBox data={ipResult} isLoading={ipIntel.isPending} />
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
