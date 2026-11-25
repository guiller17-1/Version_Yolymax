-- Ejecutar una sola vez en D1. No modifica productos, ventas ni pedidos.
CREATE TABLE IF NOT EXISTS admin_users (
 id TEXT PRIMARY KEY,
 email TEXT NOT NULL COLLATE NOCASE UNIQUE,
 name TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('owner','admin')),
 password_hash TEXT NOT NULL,
 salt TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS admin_single_owner ON admin_users(role) WHERE role='owner';
CREATE TABLE IF NOT EXISTS admin_sessions (
 token TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
 expires INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_sessions_user ON admin_sessions(user_id);
