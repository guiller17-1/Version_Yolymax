-- Ejecutar UNA sola vez, después de 0003. No elimina datos.
ALTER TABLE admin_users ADD COLUMN username TEXT COLLATE NOCASE;
CREATE UNIQUE INDEX IF NOT EXISTS admin_username_unique ON admin_users(username COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS customer_users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
 username TEXT NOT NULL COLLATE NOCASE UNIQUE,
 name TEXT NOT NULL, phone TEXT NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL,
 created_at INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),
 email_verified INTEGER NOT NULL DEFAULT 0 CHECK(email_verified IN(0,1))
);
CREATE TABLE IF NOT EXISTS customer_sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES customer_users(id) ON DELETE CASCADE, expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS customer_sessions_user ON customer_sessions(user_id);
CREATE TABLE IF NOT EXISTS customer_favorites (user_id TEXT NOT NULL REFERENCES customer_users(id) ON DELETE CASCADE, product_id TEXT NOT NULL REFERENCES products(id), PRIMARY KEY(user_id,product_id));
CREATE TABLE IF NOT EXISTS customer_carts (user_id TEXT PRIMARY KEY REFERENCES customer_users(id) ON DELETE CASCADE, items TEXT NOT NULL CHECK(json_valid(items)), version INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS orders_customer ON orders(json_extract(data,'$.customerId'));
CREATE TRIGGER IF NOT EXISTS customer_identity_insert BEFORE INSERT ON customer_users WHEN EXISTS(SELECT 1 FROM admin_users WHERE email=NEW.email COLLATE NOCASE OR username=NEW.username COLLATE NOCASE) BEGIN SELECT RAISE(ABORT,'identity already used'); END;
CREATE TRIGGER IF NOT EXISTS customer_identity_update BEFORE UPDATE OF email,username ON customer_users WHEN EXISTS(SELECT 1 FROM admin_users WHERE email=NEW.email COLLATE NOCASE OR username=NEW.username COLLATE NOCASE) BEGIN SELECT RAISE(ABORT,'identity already used'); END;
CREATE TRIGGER IF NOT EXISTS admin_identity_insert BEFORE INSERT ON admin_users WHEN EXISTS(SELECT 1 FROM customer_users WHERE email=NEW.email COLLATE NOCASE OR username=NEW.username COLLATE NOCASE) BEGIN SELECT RAISE(ABORT,'identity already used'); END;
CREATE TRIGGER IF NOT EXISTS admin_identity_update BEFORE UPDATE OF email,username ON admin_users WHEN EXISTS(SELECT 1 FROM customer_users WHERE email=NEW.email COLLATE NOCASE OR username=NEW.username COLLATE NOCASE) BEGIN SELECT RAISE(ABORT,'identity already used'); END;
