import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useLogin } from "@workspace/api-client-react";
import { useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { getGetSessionQueryKey } from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Lock, KeyRound } from "lucide-react";
import { GodsAppLogo } from "@/components/logo";

const schema = z.object({
  password: z.string().min(1, "Password required"),
});

type FormData = z.infer<typeof schema>;

export default function LockPage() {
  const [, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const login = useLogin();

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { password: "" },
  });

  const onSubmit = (data: FormData) => {
    login.mutate({ data: { password: data.password } }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetSessionQueryKey() });
        setLocation("/dashboard");
      },
      onError: () => {
        form.setError("password", { message: "Incorrect password" });
      }
    });
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex items-center justify-center">
            <div className="absolute inset-0 bg-primary/10 blur-3xl rounded-full scale-[2]" />
            <GodsAppLogo size={64} showText={false} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-wider">GODS<span className="text-primary">APP</span></h1>
            <p className="text-xs text-muted-foreground tracking-widest uppercase mt-1 font-mono">Session Locked</p>
          </div>
        </div>

        {/* Lock form */}
        <div className="border border-primary/15 rounded-lg p-6 glass-card space-y-5 shadow-[0_0_30px_rgba(34,211,238,0.05)]">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Lock className="h-4 w-4" />
            <span className="text-xs uppercase tracking-widest font-medium">Authentication Required</span>
          </div>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField control={form.control} name="password" render={({ field }) => (
                <FormItem>
                  <FormLabel className="flex items-center gap-1.5">
                    <KeyRound className="h-3.5 w-3.5" />
                    Master Password
                  </FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="Enter your master password"
                      autoFocus
                      {...field}
                      data-testid="input-master-password"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />
              <Button
                type="submit"
                className="w-full"
                disabled={login.isPending}
                data-testid="button-unlock"
              >
                {login.isPending ? "Verifying..." : "Unlock Session"}
              </Button>
            </form>
          </Form>
        </div>

        <p className="text-center text-xs text-muted-foreground">
          GodsApp Security Suite — All sessions are logged
        </p>
      </div>
    </div>
  );
}
