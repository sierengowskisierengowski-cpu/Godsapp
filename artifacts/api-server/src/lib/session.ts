import session from "express-session";
import ConnectPgSimple from "connect-pg-simple";
import { logger } from "./logger";

const PgSession = ConnectPgSimple(session);

declare module "express-session" {
  interface SessionData {
    authenticated: boolean;
    locked: boolean;
    lockedAt?: string;
  }
}

const sessionSecret = process.env.SESSION_SECRET;
if (!sessionSecret) {
  logger.warn("SESSION_SECRET not set — using fallback (unsafe for production)");
}

export const sessionMiddleware = session({
  store: new PgSession({
    conString: process.env.DATABASE_URL,
    tableName: "sessions",
    createTableIfMissing: true,
  }),
  secret: sessionSecret ?? "gods-app-dev-secret",
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === "production",
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000,
    sameSite: "lax",
  },
});

export function requireAuth(
  req: import("express").Request,
  res: import("express").Response,
  next: import("express").NextFunction
) {
  if (!req.session.authenticated || req.session.locked) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  next();
}
