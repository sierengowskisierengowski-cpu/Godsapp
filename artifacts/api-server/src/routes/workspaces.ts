import { Router } from "express";
import { db } from "@workspace/db";
import { workspacesTable, scansTable, findingsTable } from "@workspace/db";
import { eq, count } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

router.get("/workspaces", requireAuth, async (_req, res) => {
  const workspaces = await db.select().from(workspacesTable).orderBy(workspacesTable.createdAt);
  res.json(workspaces);
});

router.post("/workspaces", requireAuth, async (req, res) => {
  const { name, description, target, type } = req.body;
  if (!name) { res.status(400).json({ error: "Name required" }); return; }
  const [ws] = await db.insert(workspacesTable).values({ name, description, target, type: type ?? "pentest" }).returning();
  await logAudit("workspace.created", { resource: "workspace", resourceId: ws.id, req });
  res.status(201).json(ws);
});

router.get("/workspaces/:id", requireAuth, async (req, res) => {
  const [ws] = await db.select().from(workspacesTable).where(eq(workspacesTable.id, req.params.id)).limit(1);
  if (!ws) { res.status(404).json({ error: "Workspace not found" }); return; }
  res.json(ws);
});

router.put("/workspaces/:id", requireAuth, async (req, res) => {
  const { name, description, target, type, status } = req.body;
  const [ws] = await db.update(workspacesTable).set({ name, description, target, type, status }).where(eq(workspacesTable.id, req.params.id)).returning();
  if (!ws) { res.status(404).json({ error: "Workspace not found" }); return; }
  await logAudit("workspace.updated", { resource: "workspace", resourceId: ws.id, req });
  res.json(ws);
});

router.delete("/workspaces/:id", requireAuth, async (req, res) => {
  const [ws] = await db.delete(workspacesTable).where(eq(workspacesTable.id, req.params.id)).returning();
  if (!ws) { res.status(404).json({ error: "Workspace not found" }); return; }
  await logAudit("workspace.deleted", { resource: "workspace", resourceId: req.params.id, req });
  res.json({ success: true });
});

router.get("/workspaces/:id/stats", requireAuth, async (req, res) => {
  const wid = req.params.id;
  const [scanCount] = await db.select({ count: count() }).from(scansTable).where(eq(scansTable.workspaceId, wid));
  const findingsBySeverity = await db.select({ severity: findingsTable.severity, count: count() }).from(findingsTable).where(eq(findingsTable.workspaceId, wid)).groupBy(findingsTable.severity);
  const severityMap: Record<string, number> = {};
  for (const row of findingsBySeverity) severityMap[row.severity] = Number(row.count);
  res.json({
    scans: Number(scanCount?.count ?? 0),
    findings: Object.values(severityMap).reduce((a, b) => a + b, 0),
    critical: severityMap["critical"] ?? 0, high: severityMap["high"] ?? 0,
    medium: severityMap["medium"] ?? 0, low: severityMap["low"] ?? 0, info: severityMap["info"] ?? 0,
  });
});

export default router;
