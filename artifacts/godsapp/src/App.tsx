import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "next-themes";
import NotFound from "@/pages/not-found";
import { AuthGate } from "@/components/auth-gate";

import Dashboard from "@/pages/dashboard";
import Setup from "@/pages/setup";
import Lock from "@/pages/lock";
import Workspaces from "@/pages/workspaces";
import WorkspaceDetail from "@/pages/workspace-detail";
import Findings from "@/pages/findings";
import Evidence from "@/pages/evidence";
import Reports from "@/pages/reports";
import Scheduler from "@/pages/scheduler";
import Plugins from "@/pages/plugins";
import Settings from "@/pages/settings";
import NetworkTools from "@/pages/tools/network";
import WebTools from "@/pages/tools/web";
import CryptoTools from "@/pages/tools/crypto";
import ExploitationTools from "@/pages/tools/exploitation";
import IntelTools from "@/pages/tools/intel";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

function MainApp() {
  return (
    <AuthGate>
      <Switch>
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/workspaces" component={Workspaces} />
        <Route path="/workspaces/:id" component={WorkspaceDetail} />
        <Route path="/findings" component={Findings} />
        <Route path="/evidence" component={Evidence} />
        <Route path="/reports" component={Reports} />
        <Route path="/scheduler" component={Scheduler} />
        <Route path="/plugins" component={Plugins} />
        <Route path="/settings" component={Settings} />
        <Route path="/tools/network" component={NetworkTools} />
        <Route path="/tools/web" component={WebTools} />
        <Route path="/tools/crypto" component={CryptoTools} />
        <Route path="/tools/exploitation" component={ExploitationTools} />
        <Route path="/tools/intel" component={IntelTools} />
        <Route path="/" component={Dashboard} />
        <Route component={NotFound} />
      </Switch>
    </AuthGate>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/setup" component={Setup} />
      <Route path="/lock" component={Lock} />
      <Route path="/:rest*" component={MainApp} />
    </Switch>
  );
}

function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Router />
          </WouterRouter>
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
