# Catálogo de Productos y Gestión de Pedidos

Aplicación web con Flask, SQLAlchemy y PostgreSQL para catálogo de productos, reserva automática de stock y panel administrativo.

## Variables de Entorno requeridas:
- `DATABASE_URL`: URI de conexión a Neon PostgreSQL.
- `SECRET_KEY`: Clave secreta de sesión Flask.
- `ADMIN_PASSWORD`: Contraseña para ingresar al panel administrador.
- `CRON_SECRET`: Token para ejecutar la captura de stock diaria.
- `ONEDRIVE_URL`: URL pública de descarga directa del Excel en OneDrive.
