import { useGetSession, useGetSetupStatus } from "@workspace/api-client-react";
import { Spinner } from "@/components/ui/spinner";
import SetupPage from "@/pages/setup";
import LockPage from "@/pages/lock";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { data: setupStatus, isLoading: isLoadingSetup } = useGetSetupStatus();
  const { data: session, isLoading: isLoadingSession, error } = useGetSession({
    query: { retry: false }
  });

  if (isLoadingSetup || isLoadingSession) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background text-foreground">
        <Spinner className="w-8 h-8 text-primary" />
      </div>
    );
  }

  if (setupStatus && !setupStatus.completed) {
    return <SetupPage />;
  }

  if (error || !session?.authenticated || session?.locked) {
    return <LockPage />;
  }

  return <>{children}</>;
}
