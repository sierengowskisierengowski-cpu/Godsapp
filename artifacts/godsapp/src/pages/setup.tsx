import { useState } from "react";
import { useLocation } from "wouter";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCompleteSetup } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { getGetSetupStatusQueryKey, getGetSessionQueryKey } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Lock, User, ArrowRight, CheckCircle } from "lucide-react";
import { GodsAppLogo } from "@/components/logo";
import { cn } from "@/lib/utils";

const STEPS = ["Welcome", "Operator", "Master Password", "Complete"];

const step2Schema = z.object({
  operatorName: z.string().min(2, "Name must be at least 2 characters"),
  organization: z.string().optional(),
});

const step3Schema = z.object({
  password: z.string().min(14, "Password must be at least 14 characters"),
  confirm: z.string(),
}).refine(d => d.password === d.confirm, { message: "Passwords do not match", path: ["confirm"] });

type Step2Data = z.infer<typeof step2Schema>;
type Step3Data = z.infer<typeof step3Schema>;

export default function Setup() {
  const [step, setStep] = useState(0);
  const [operatorData, setOperatorData] = useState<Step2Data>({ operatorName: "", organization: "" });
  const [, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const completeSetup = useCompleteSetup();

  const step2Form = useForm<Step2Data>({ resolver: zodResolver(step2Schema), defaultValues: operatorData });
  const step3Form = useForm<Step3Data>({ resolver: zodResolver(step3Schema), defaultValues: { password: "", confirm: "" } });

  const onStep2 = (data: Step2Data) => {
    setOperatorData(data);
    setStep(2);
  };

  const onStep3 = (data: Step3Data) => {
    completeSetup.mutate({
      data: {
        password: data.password,
        operatorName: operatorData.operatorName,
        organization: operatorData.organization,
      }
    }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetSetupStatusQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetSessionQueryKey() });
        setStep(3);
        setTimeout(() => setLocation("/dashboard"), 1500);
      }
    });
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="relative">
            <div className="absolute inset-0 bg-primary/15 blur-3xl rounded-full scale-150" />
            <GodsAppLogo size={56} showText={false} scrambleOnMount />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-wider">GODS<span className="text-primary">APP</span></h1>
            <p className="text-xs text-muted-foreground tracking-widest uppercase mt-0.5 font-mono">Security Research Suite</p>
          </div>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={cn(
                "flex items-center justify-center h-6 w-6 rounded-full text-xs font-semibold border flex-shrink-0 transition-colors",
                i < step ? "bg-primary border-primary text-primary-foreground" :
                i === step ? "border-primary text-primary" :
                "border-border text-muted-foreground"
              )}>
                {i < step ? <CheckCircle className="h-3.5 w-3.5" /> : i + 1}
              </div>
              {!((step === 3) && i === 2) && i < STEPS.length - 1 && (
                <div className={cn("h-px flex-1", i < step ? "bg-primary" : "bg-border")} />
              )}
            </div>
          ))}
        </div>

        {/* Step 0: Welcome */}
        {step === 0 && (
          <div className="space-y-6">
            <div className="border border-border rounded-lg p-6 bg-card space-y-4">
              <h2 className="text-xl font-semibold">Welcome to GodsApp</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                GodsApp is a professional-grade security auditing and research suite.
                This setup wizard will configure your operator profile and master password —
                a single strong passphrase that protects all sessions.
              </p>
              <ul className="space-y-2 text-sm text-muted-foreground">
                {[
                  "All data is stored locally in your database",
                  "Master password must be at least 14 characters",
                  "Session locks automatically on inactivity",
                  "Full audit log of all operations",
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <Button className="w-full gap-2" onClick={() => setStep(1)} data-testid="button-setup-begin">
              Begin Setup <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Step 1: Operator Profile */}
        {step === 1 && (
          <Form {...step2Form}>
            <form onSubmit={step2Form.handleSubmit(onStep2)} className="space-y-4">
              <div className="border border-border rounded-lg p-6 bg-card space-y-4">
                <div className="flex items-center gap-2">
                  <User className="h-5 w-5 text-primary" />
                  <h2 className="text-xl font-semibold">Operator Profile</h2>
                </div>
                <FormField control={step2Form.control} name="operatorName" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Operator Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. J. Sierengowski" {...field} data-testid="input-operator-name" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={step2Form.control} name="organization" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Organization <span className="text-muted-foreground">(optional)</span></FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Red Team LLC" {...field} data-testid="input-organization" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => setStep(0)} className="flex-1">Back</Button>
                <Button type="submit" className="flex-1 gap-2" data-testid="button-setup-next">
                  Continue <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </Form>
        )}

        {/* Step 2: Master Password */}
        {step === 2 && (
          <Form {...step3Form}>
            <form onSubmit={step3Form.handleSubmit(onStep3)} className="space-y-4">
              <div className="border border-border rounded-lg p-6 bg-card space-y-4">
                <div className="flex items-center gap-2">
                  <Lock className="h-5 w-5 text-primary" />
                  <h2 className="text-xl font-semibold">Master Password</h2>
                </div>
                <p className="text-sm text-muted-foreground">
                  Choose a strong passphrase of at least 14 characters. This is the only password you'll need.
                </p>
                <FormField control={step3Form.control} name="password" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Master Password</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Minimum 14 characters" {...field} data-testid="input-master-password" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={step3Form.control} name="confirm" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm Password</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Repeat your password" {...field} data-testid="input-confirm-password" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                {completeSetup.error && (
                  <p className="text-sm text-destructive">{String(completeSetup.error)}</p>
                )}
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => setStep(1)} className="flex-1">Back</Button>
                <Button type="submit" className="flex-1 gap-2" disabled={completeSetup.isPending} data-testid="button-setup-finish">
                  {completeSetup.isPending ? "Setting up..." : "Complete Setup"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </form>
          </Form>
        )}

        {/* Step 3: Complete */}
        {step === 3 && (
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="relative">
                <div className="absolute inset-0 bg-primary/20 blur-2xl rounded-full" />
                <CheckCircle className="h-16 w-16 text-primary relative" />
              </div>
            </div>
            <h2 className="text-xl font-semibold">Setup Complete</h2>
            <p className="text-sm text-muted-foreground">
              GodsApp is ready. Redirecting to your dashboard...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
