import { Router } from "express";
import bcrypt from "bcryptjs";
import { db } from "@workspace/db";
import { appSettingsTable, auditLogTable } from "@workspace/db";
import { eq, desc } from "drizzle-orm";
import { requireAuth } from "../lib/session";
import { logAudit } from "../lib/audit";

const router = Router();

router.get("/auth/setup/status", async (_req, res) => {
  const settings = await db.select().from(appSettingsTable).limit(1);
  const completed = settings.length > 0 && settings[0].setupCompleted;
  res.json({ completed: !!completed });
});

router.post("/auth/setup", async (req, res) => {
  const existing = await db.select().from(appSettingsTable).limit(1);
  if (existing.length > 0 && existing[0].setupCompleted) {
    res.status(400).json({ error: "Setup already completed" });
    return;
  }
  const { password, operatorName, organization } = req.body;
  if (!password || password.length < 14) {
    res.status(400).json({ error: "Password must be at least 14 characters" });
    return;
  }
  const passwordHash = await bcrypt.hash(password, 12);
  if (existing.length === 0) {
    await db.insert(appSettingsTable).values({
      setupCompleted: true,
      passwordHash,
      operatorName: operatorName ?? "Operator",
      organization: organization ?? null,
    });
  } else {
    await db.update(appSettingsTable)
      .set({ setupCompleted: true, passwordHash, operatorName, organization })
      .where(eq(appSettingsTable.id, existing[0].id));
  }
  req.session.authenticated = true;
  req.session.locked = false;
  await logAudit("setup.completed", { req });
  res.json({ success: true });
});

router.post("/auth/login", async (req, res) => {
  const { password } = req.body;
  if (!password) {
    res.status(400).json({ error: "Password required" });
    return;
  }
  const settings = await db.select().from(appSettingsTable).limit(1);
  if (!settings.length || !settings[0].setupCompleted || !settings[0].passwordHash) {
    res.status(400).json({ error: "Setup not completed" });
    return;
  }
  const valid = await bcrypt.compare(password, settings[0].passwordHash);
  if (!valid) {
    await logAudit("auth.failed", { req });
    res.status(401).json({ error: "Invalid password" });
    return;
  }
  req.session.authenticated = true;
  req.session.locked = false;
  await logAudit("auth.login", { req });
  res.json({ success: true, operatorName: settings[0].operatorName });
});

router.post("/auth/lock", requireAuth, async (req, res) => {
  req.session.locked = true;
  req.session.lockedAt = new Date().toISOString();
  await logAudit("auth.locked", { req });
  res.json({ success: true });
});

router.get("/auth/session", (req, res) => {
  if (!req.session.authenticated) {
    res.status(401).json({ authenticated: false, locked: false });
    return;
  }
  res.json({ authenticated: true, locked: !!req.session.locked });
});

router.post("/auth/password", requireAuth, async (req, res) => {
  const { currentPassword, newPassword } = req.body;
  if (!currentPassword || !newPassword || newPassword.length < 14) {
    res.status(400).json({ error: "New password must be at least 14 characters" });
    return;
  }
  const settings = await db.select().from(appSettingsTable).limit(1);
  if (!settings.length || !settings[0].passwordHash) {
    res.status(400).json({ error: "Setup not completed" });
    return;
  }
  const valid = await bcrypt.compare(currentPassword, settings[0].passwordHash);
  if (!valid) {
    res.status(401).json({ error: "Current password incorrect" });
    return;
  }
  const newHash = await bcrypt.hash(newPassword, 12);
  await db.update(appSettingsTable).set({ passwordHash: newHash }).where(eq(appSettingsTable.id, settings[0].id));
  await logAudit("auth.password_changed", { req });
  res.json({ success: true });
});

router.get("/auth/audit-log", requireAuth, async (req, res) => {
  const limit = parseInt(req.query.limit as string) || 50;
  const offset = parseInt(req.query.offset as string) || 0;
  const logs = await db.select().from(auditLogTable)
    .orderBy(desc(auditLogTable.timestamp))
    .limit(limit)
    .offset(offset);
  res.json(logs);
});

export default router;
