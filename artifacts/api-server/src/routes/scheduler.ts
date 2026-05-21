import { Router } from "express";
import { db } from "@workspace/db";
import { schedulesTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

router.get("/workspaces/:workspaceId/schedules", requireAuth, async (req, res) => {
  const schedules = await db.select().from(schedulesTable).where(eq(schedulesTable.workspaceId, req.params.workspaceId)).orderBy(schedulesTable.createdAt);
  res.json(schedules);
});

router.post("/workspaces/:workspaceId/schedules", requireAuth, async (req, res) => {
  const { name, scanConfig, cron, enabled } = req.body;
  if (!name || !cron) { res.status(400).json({ error: "name and cron are required" }); return; }
  const [schedule] = await db.insert(schedulesTable).values({ workspaceId: req.params.workspaceId, name, scanConfig: typeof scanConfig === "object" ? JSON.stringify(scanConfig) : (scanConfig ?? "{}"), cron, enabled: enabled !== false }).returning();
  await logAudit("schedule.created", { resource: "schedule", resourceId: schedule.id, req });
  res.status(201).json(schedule);
});

router.delete("/workspaces/:workspaceId/schedules/:scheduleId", requireAuth, async (req, res) => {
  const [schedule] = await db.delete(schedulesTable).where(and(eq(schedulesTable.id, req.params.scheduleId), eq(schedulesTable.workspaceId, req.params.workspaceId))).returning();
  if (!schedule) { res.status(404).json({ error: "Schedule not found" }); return; }
  await logAudit("schedule.deleted", { resource: "schedule", resourceId: req.params.scheduleId, req });
  res.json({ success: true });
});

export default router;
