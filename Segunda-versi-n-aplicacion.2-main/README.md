# Catálogo con pedidos y reservas

## Funciones
- Inventario diario desde Excel de OneDrive.
- Captura diaria a las 6:00 a. m. de Lima mediante Render Cron (`0 11 * * *` UTC).
- Pedidos pendientes que reservan stock.
- Confirmación o rechazo desde `/admin/pedidos`.
- Los pedidos no se eliminan al cambiar de estado.
- Exportación acumulada a Excel desde el panel.
- Formulario de nombre y celular antes de abrir WhatsApp.
- La cesta se limpia después de registrar correctamente el pedido.

## Variables de entorno
Configura en Render:
- `ONEDRIVE_URL`
- `DATABASE_URL` (la crea el Blueprint)
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `CRON_SECRET`
- `APP_BASE_URL` (por ejemplo `https://tu-app.onrender.com`)

Usa el mismo valor de `CRON_SECRET` en el servicio web y en el cron.

## Excel de inventario
Hoja: `Inventario`
Columnas obligatorias:
- Marca
- Producto
- Stock Actual
- Precio
- Imagen 1
- Imagen 2
- Imagen 3

## Reglas de stock
- Pendiente: reserva stock.
- Confirmado: mantiene el stock descontado.
- Rechazado: libera la reserva.
- Cada día, la nueva captura del Excel reemplaza la base de cálculo del día.

## Despliegue
1. Sube todos los archivos a GitHub.
2. En Render, crea un Blueprint usando `render.yaml`.
3. Configura las variables marcadas como `sync: false`.
4. Entra a `/admin/login` y usa `ADMIN_PASSWORD`.

## Nota
La ruta administrativa no es secreta por sí sola. Está protegida con contraseña y sesión.
