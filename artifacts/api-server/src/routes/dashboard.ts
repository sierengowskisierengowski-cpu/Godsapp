import { Router } from "express";
import { db } from "@workspace/db";
import { workspacesTable, scansTable, findingsTable, auditLogTable } from "@workspace/db";
import { eq, count, desc, sql } from "drizzle-orm";
import { requireAuth } from "../lib/session";

const router = Router();

router.get("/dashboard/stats", requireAuth, async (_req, res) => {
  const [wsCount] = await db.select({ count: count() }).from(workspacesTable);
  const [activeWsCount] = await db.select({ count: count() }).from(workspacesTable).where(eq(workspacesTable.status, "active"));
  const [activeScansCount] = await db.select({ count: count() }).from(scansTable).where(eq(scansTable.status, "running"));
  const [totalFindings] = await db.select({ count: count() }).from(findingsTable);
  const [criticalFindings] = await db.select({ count: count() }).from(findingsTable).where(eq(findingsTable.severity, "critical"));
  const [scansToday] = await db.select({ count: count() }).from(scansTable).where(sql`DATE(${scansTable.createdAt}) = CURRENT_DATE`);
  res.json({
    workspaceCount: Number(wsCount?.count ?? 0),
    activeWorkspaceCount: Number(activeWsCount?.count ?? 0),
    activeScans: Number(activeScansCount?.count ?? 0),
    totalFindings: Number(totalFindings?.count ?? 0),
    criticalFindings: Number(criticalFindings?.count ?? 0),
    scansToday: Number(scansToday?.count ?? 0),
  });
});

router.get("/dashboard/recent-activity", requireAuth, async (req, res) => {
  const limit = parseInt(req.query.limit as string) || 20;
  const logs = await db.select().from(auditLogTable).orderBy(desc(auditLogTable.timestamp)).limit(limit);
  res.json(logs);
});

router.get("/dashboard/active-scans", requireAuth, async (_req, res) => {
  const scans = await db.select().from(scansTable).where(eq(scansTable.status, "running")).orderBy(desc(scansTable.startedAt)).limit(20);
  res.json(scans);
});

export default router;
