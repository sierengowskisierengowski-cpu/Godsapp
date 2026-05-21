import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCalculateHash, useEncodeText, useIdentifyHash } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Binary, Loader2, Hash, Search, Copy } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const hashSchema = z.object({ text: z.string().min(1), algorithm: z.string().default("sha256") });
const encodeSchema = z.object({ text: z.string().min(1), encoding: z.string().default("base64"), action: z.string().default("encode") });
const identifySchema = z.object({ hash: z.string().min(1) });

export default function CryptoTools() {
  const [hashResult, setHashResult] = useState<{ hash: string; algorithm: string } | null>(null);
  const [encodeResult, setEncodeResult] = useState<{ result: string; encoding: string; action: string } | null>(null);
  const [identifyResult, setIdentifyResult] = useState<{ candidates: { name: string; confidence: string }[] } | null>(null);
  const { toast } = useToast();

  const calcHash = useCalculateHash();
  const encodeText = useEncodeText();
  const identifyHashMut = useIdentifyHash();

  const hashForm = useForm({ resolver: zodResolver(hashSchema), defaultValues: { text: "", algorithm: "sha256" } });
  const encodeForm = useForm({ resolver: zodResolver(encodeSchema), defaultValues: { text: "", encoding: "base64", action: "encode" } });
  const identifyForm = useForm({ resolver: zodResolver(identifySchema), defaultValues: { hash: "" } });

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({ title: "Copied to clipboard" });
  };

  return (
    <Layout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Binary className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Crypto & Encoding</h1>
            <p className="text-sm text-muted-foreground">Hash calculator, text encoder, hash identifier</p>
          </div>
        </div>

        <Tabs defaultValue="hash">
          <TabsList className="mb-6">
            <TabsTrigger value="hash" data-testid="tab-hash">Hash Calculator</TabsTrigger>
            <TabsTrigger value="encode" data-testid="tab-encode">Encoder</TabsTrigger>
            <TabsTrigger value="identify" data-testid="tab-identify">Hash Identifier</TabsTrigger>
          </TabsList>

          <TabsContent value="hash" className="space-y-4">
            <Form {...hashForm}>
              <form onSubmit={hashForm.handleSubmit(d => {
                calcHash.mutate({ data: d }, { onSuccess: (r) => setHashResult(r as typeof hashResult) });
              })} className="space-y-3">
                <FormField control={hashForm.control} name="text" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Input Text</FormLabel>
                    <FormControl><Textarea placeholder="Enter text to hash" rows={3} {...field} data-testid="input-hash-text" /></FormControl>
                  </FormItem>
                )} />
                <div className="flex gap-2">
                  <FormField control={hashForm.control} name="algorithm" render={({ field }) => (
                    <FormItem className="flex-1">
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger data-testid="select-hash-algorithm"><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          {["md5","sha1","sha224","sha256","sha384","sha512"].map(a => <SelectItem key={a} value={a}>{a.toUpperCase()}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />
                  <Button type="submit" disabled={calcHash.isPending} className="gap-2" data-testid="button-calculate-hash">
                    {calcHash.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Hash className="h-4 w-4" />}
                    Calculate
                  </Button>
                </div>
              </form>
            </Form>
            {hashResult && (
              <div className="border border-border rounded-lg p-4 bg-card space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">{hashResult.algorithm}</span>
                  <Button variant="ghost" size="sm" onClick={() => copy(hashResult.hash)} className="h-6 gap-1.5 text-xs">
                    <Copy className="h-3 w-3" /> Copy
                  </Button>
                </div>
                <p className="font-mono text-sm text-primary break-all">{hashResult.hash}</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="encode" className="space-y-4">
            <Form {...encodeForm}>
              <form onSubmit={encodeForm.handleSubmit(d => {
                encodeText.mutate({ data: d }, { onSuccess: (r) => setEncodeResult(r as typeof encodeResult) });
              })} className="space-y-3">
                <FormField control={encodeForm.control} name="text" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Input</FormLabel>
                    <FormControl><Textarea placeholder="Enter text to encode/decode" rows={3} {...field} data-testid="input-encode-text" /></FormControl>
                  </FormItem>
                )} />
                <div className="flex gap-2">
                  <FormField control={encodeForm.control} name="encoding" render={({ field }) => (
                    <FormItem className="flex-1">
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger data-testid="select-encoding"><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          {["base64","hex","url","html","rot13"].map(e => <SelectItem key={e} value={e}>{e.toUpperCase()}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />
                  <FormField control={encodeForm.control} name="action" render={({ field }) => (
                    <FormItem className="w-32">
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl><SelectTrigger data-testid="select-encode-action"><SelectValue /></SelectTrigger></FormControl>
                        <SelectContent>
                          <SelectItem value="encode">Encode</SelectItem>
                          <SelectItem value="decode">Decode</SelectItem>
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />
                  <Button type="submit" disabled={encodeText.isPending} className="gap-2" data-testid="button-encode">
                    {encodeText.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Binary className="h-4 w-4" />}
                    Run
                  </Button>
                </div>
              </form>
            </Form>
            {encodeResult && (
              <div className="border border-border rounded-lg p-4 bg-card space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">{encodeResult.encoding} — {encodeResult.action}</span>
                  <Button variant="ghost" size="sm" onClick={() => copy(encodeResult.result)} className="h-6 gap-1.5 text-xs">
                    <Copy className="h-3 w-3" /> Copy
                  </Button>
                </div>
                <p className="font-mono text-sm text-primary break-all">{encodeResult.result}</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="identify" className="space-y-4">
            <Form {...identifyForm}>
              <form onSubmit={identifyForm.handleSubmit(d => {
                identifyHashMut.mutate({ data: d }, { onSuccess: (r) => setIdentifyResult(r as typeof identifyResult) });
              })} className="flex gap-2">
                <FormField control={identifyForm.control} name="hash" render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl><Input placeholder="Paste hash to identify" {...field} data-testid="input-identify-hash" className="font-mono text-sm" /></FormControl>
                  </FormItem>
                )} />
                <Button type="submit" disabled={identifyHashMut.isPending} className="gap-2" data-testid="button-identify-hash">
                  {identifyHashMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Identify
                </Button>
              </form>
            </Form>
            {identifyResult?.candidates && (
              <div className="border border-border rounded-lg p-4 bg-card space-y-3">
                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Candidates</span>
                <div className="flex flex-wrap gap-2">
                  {identifyResult.candidates.map((c, i) => (
                    <Badge key={i} variant="outline" className="gap-1.5">
                      <span className="font-semibold">{c.name}</span>
                      <span className="text-muted-foreground text-xs">{c.confidence}</span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}
