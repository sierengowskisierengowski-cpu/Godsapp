import { Router } from "express";
import { db } from "@workspace/db";
import { scansTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

router.get("/workspaces/:workspaceId/scans", requireAuth, async (req, res) => {
  const scans = await db.select().from(scansTable).where(eq(scansTable.workspaceId, req.params.workspaceId)).orderBy(scansTable.createdAt);
  res.json(scans);
});

router.post("/workspaces/:workspaceId/scans", requireAuth, async (req, res) => {
  const { name, target, tool, config } = req.body;
  if (!name || !target || !tool) { res.status(400).json({ error: "name, target, and tool are required" }); return; }
  const [scan] = await db.insert(scansTable).values({ workspaceId: req.params.workspaceId, name, target, tool, config: config ? JSON.stringify(config) : null, status: "pending" }).returning();
  await logAudit("scan.created", { resource: "scan", resourceId: scan.id, req });
  res.status(201).json(scan);
});

router.get("/workspaces/:workspaceId/scans/:scanId", requireAuth, async (req, res) => {
  const [scan] = await db.select().from(scansTable).where(and(eq(scansTable.id, req.params.scanId), eq(scansTable.workspaceId, req.params.workspaceId))).limit(1);
  if (!scan) { res.status(404).json({ error: "Scan not found" }); return; }
  res.json(scan);
});

router.delete("/workspaces/:workspaceId/scans/:scanId", requireAuth, async (req, res) => {
  const [scan] = await db.delete(scansTable).where(and(eq(scansTable.id, req.params.scanId), eq(scansTable.workspaceId, req.params.workspaceId))).returning();
  if (!scan) { res.status(404).json({ error: "Scan not found" }); return; }
  await logAudit("scan.deleted", { resource: "scan", resourceId: req.params.scanId, req });
  res.json({ success: true });
});

router.post("/workspaces/:workspaceId/scans/:scanId/stop", requireAuth, async (req, res) => {
  const [scan] = await db.update(scansTable).set({ status: "stopped", completedAt: new Date() }).where(and(eq(scansTable.id, req.params.scanId), eq(scansTable.workspaceId, req.params.workspaceId))).returning();
  if (!scan) { res.status(404).json({ error: "Scan not found" }); return; }
  await logAudit("scan.stopped", { resource: "scan", resourceId: req.params.scanId, req });
  res.json(scan);
});

router.post("/workspaces/:workspaceId/scans/:scanId/replay", requireAuth, async (req, res) => {
  const [original] = await db.select().from(scansTable).where(and(eq(scansTable.id, req.params.scanId), eq(scansTable.workspaceId, req.params.workspaceId))).limit(1);
  if (!original) { res.status(404).json({ error: "Scan not found" }); return; }
  const [replay] = await db.insert(scansTable).values({ workspaceId: original.workspaceId, name: `${original.name} (Replay)`, target: original.target, tool: original.tool, config: original.config, status: "pending" }).returning();
  await logAudit("scan.replayed", { resource: "scan", resourceId: replay.id, req });
  res.status(201).json(replay);
});

export default router;
