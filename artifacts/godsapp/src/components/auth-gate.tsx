import { useEffect } from "react";
import { useLocation } from "wouter";
import { useGetSession, useGetSetupStatus } from "@workspace/api-client-react";
import { Spinner } from "@/components/ui/spinner";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [, setLocation] = useLocation();
  const { data: setupStatus, isLoading: isLoadingSetup } = useGetSetupStatus();
  const { data: session, isLoading: isLoadingSession, error } = useGetSession({
    query: {
      retry: false,
    }
  });

  useEffect(() => {
    if (isLoadingSetup || isLoadingSession) return;

    if (setupStatus && !setupStatus.completed) {
      setLocation("/setup");
      return;
    }

    if (error || !session?.authenticated) {
      setLocation("/lock");
      return;
    }
    
    if (session?.locked) {
      setLocation("/lock");
      return;
    }
  }, [setupStatus, session, isLoadingSetup, isLoadingSession, error, setLocation]);

  if (isLoadingSetup || isLoadingSession) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background text-foreground">
        <Spinner className="w-8 h-8 text-primary" />
      </div>
    );
  }

  if (!setupStatus?.completed || !session?.authenticated || session?.locked) {
    return null; // Will redirect in effect
  }

  return <>{children}</>;
}
