import { db } from "@workspace/db";
import { auditLogTable } from "@workspace/db";
import type { Request } from "express";

export async function logAudit(
  action: string,
  options?: {
    resource?: string;
    resourceId?: string;
    detail?: string;
    req?: Request;
  }
) {
  try {
    await db.insert(auditLogTable).values({
      action,
      resource: options?.resource,
      resourceId: options?.resourceId,
      detail: options?.detail,
      ip: options?.req ? (
        (options.req.headers["x-forwarded-for"] as string)?.split(",")[0]?.trim() ||
        options.req.socket.remoteAddress ||
        null
      ) : null,
    });
  } catch {
    // audit log failures are non-fatal
  }
}
