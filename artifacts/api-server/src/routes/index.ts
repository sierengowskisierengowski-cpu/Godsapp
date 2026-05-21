import { Router, type IRouter } from "express";
import healthRouter from "./health";
import authRouter from "./auth";
import settingsRouter from "./settings";
import workspacesRouter from "./workspaces";
import scansRouter from "./scans";
import findingsRouter from "./findings";
import evidenceRouter from "./evidence";
import dashboardRouter from "./dashboard";
import toolsRouter from "./tools";
import pluginsRouter from "./plugins";
import reportsRouter from "./reports";
import schedulerRouter from "./scheduler";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(settingsRouter);
router.use(workspacesRouter);
router.use(scansRouter);
router.use(findingsRouter);
router.use(evidenceRouter);
router.use(dashboardRouter);
router.use(toolsRouter);
router.use(pluginsRouter);
router.use(reportsRouter);
router.use(schedulerRouter);

export default router;
