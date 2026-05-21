import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAnalyzeSsl, useAnalyzeHeaders, useAnalyzeJwt } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Globe, Lock, Code, Loader2, Search, CheckCircle, XCircle } from "lucide-react";

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

function SecurityHeadersTable({ data }: { data: Record<string, string | null> }) {
  const DESCRIPTIONS: Record<string, string> = {
    "strict-transport-security": "Enforces HTTPS",
    "x-frame-options": "Clickjacking protection",
    "x-content-type-options": "MIME sniffing prevention",
    "content-security-policy": "XSS/injection mitigation",
    "x-xss-protection": "Legacy XSS filter",
    "referrer-policy": "Referrer header control",
    "permissions-policy": "Browser feature access",
  };
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="text-left px-4 py-2 font-medium text-muted-foreground">Header</th>
            <th className="text-left px-4 py-2 font-medium text-muted-foreground">Status</th>
            <th className="text-left px-4 py-2 font-medium text-muted-foreground hidden md:table-cell">Purpose</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(data).map(([key, val]) => (
            <tr key={key} className="border-t border-border">
              <td className="px-4 py-2 font-mono text-xs">{key}</td>
              <td className="px-4 py-2">
                {val ? (
                  <div className="flex items-center gap-1.5 text-green-400">
                    <CheckCircle className="h-3.5 w-3.5" />
                    <span className="text-xs truncate max-w-[200px]">{val}</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-red-400">
                    <XCircle className="h-3.5 w-3.5" />
                    <span className="text-xs">Missing</span>
                  </div>
                )}
              </td>
              <td className="px-4 py-2 text-xs text-muted-foreground hidden md:table-cell">{DESCRIPTIONS[key]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const sslSchema = z.object({ host: z.string().min(1) });
const headersSchema = z.object({ url: z.string().url("Must be a valid URL") });
const jwtSchema = z.object({ token: z.string().min(1) });

export default function WebTools() {
  const [sslResult, setSslResult] = useState<unknown>(null);
  const [headersResult, setHeadersResult] = useState<{securityHeaders?: Record<string, string|null>; [k:string]:unknown} | null>(null);
  const [jwtResult, setJwtResult] = useState<unknown>(null);

  const analyzeSsl = useAnalyzeSsl();
  const analyzeHeaders = useAnalyzeHeaders();
  const analyzeJwt = useAnalyzeJwt();

  const sslForm = useForm({ resolver: zodResolver(sslSchema), defaultValues: { host: "" } });
  const headersForm = useForm({ resolver: zodResolver(headersSchema), defaultValues: { url: "" } });
  const jwtForm = useForm({ resolver: zodResolver(jwtSchema), defaultValues: { token: "" } });

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Globe className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Web Analysis</h1>
            <p className="text-sm text-muted-foreground">SSL/TLS, HTTP headers, JWT decoder</p>
          </div>
        </div>

        <Tabs defaultValue="ssl">
          <TabsList className="mb-6">
            <TabsTrigger value="ssl" data-testid="tab-ssl">SSL/TLS</TabsTrigger>
            <TabsTrigger value="headers" data-testid="tab-headers">HTTP Headers</TabsTrigger>
            <TabsTrigger value="jwt" data-testid="tab-jwt">JWT Decoder</TabsTrigger>
          </TabsList>

          <TabsContent value="ssl" className="space-y-4">
            <Form {...sslForm}>
              <form onSubmit={sslForm.handleSubmit(d => {
                analyzeSsl.mutate({ data: d }, { onSuccess: setSslResult });
              })} className="flex gap-2">
                <FormField control={sslForm.control} name="host" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Host (e.g. example.com)" {...field} data-testid="input-ssl-host" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={analyzeSsl.isPending} className="gap-2" data-testid="button-ssl-analyze">
                  {analyzeSsl.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
                  Analyze
                </Button>
              </form>
            </Form>
            <ResultBox data={sslResult} isLoading={analyzeSsl.isPending} />
          </TabsContent>

          <TabsContent value="headers" className="space-y-4">
            <Form {...headersForm}>
              <form onSubmit={headersForm.handleSubmit(d => {
                analyzeHeaders.mutate({ data: d }, { onSuccess: (data) => setHeadersResult(data as typeof headersResult) });
              })} className="flex gap-2">
                <FormField control={headersForm.control} name="url" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="URL (e.g. https://example.com)" {...field} data-testid="input-headers-url" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={analyzeHeaders.isPending} className="gap-2" data-testid="button-headers-analyze">
                  {analyzeHeaders.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Analyze
                </Button>
              </form>
            </Form>
            {headersResult?.securityHeaders ? (
              <div className="space-y-3">
                <SecurityHeadersTable data={headersResult.securityHeaders} />
              </div>
            ) : (
              <div className="flex items-center justify-center h-32 border border-dashed border-border rounded-lg text-muted-foreground text-sm">
                {analyzeHeaders.isPending ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : "Enter a URL to analyze security headers"}
              </div>
            )}
          </TabsContent>

          <TabsContent value="jwt" className="space-y-4">
            <Form {...jwtForm}>
              <form onSubmit={jwtForm.handleSubmit(d => {
                analyzeJwt.mutate({ data: d }, { onSuccess: setJwtResult });
              })} className="flex gap-2">
                <FormField control={jwtForm.control} name="token" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Paste JWT token here" {...field} data-testid="input-jwt-token" className="font-mono text-xs" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={analyzeJwt.isPending} className="gap-2" data-testid="button-jwt-decode">
                  {analyzeJwt.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Code className="h-4 w-4" />}
                  Decode
                </Button>
              </form>
            </Form>
            <ResultBox data={jwtResult} isLoading={analyzeJwt.isPending} />
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
