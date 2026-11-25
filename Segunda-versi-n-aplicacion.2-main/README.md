# YOLYMAX V1 — Cloudflare Workers

Versión inicial conectada a servidor, basada en el HTML V3 aprobado. Incluye catálogo, fotografías de cinco promociones, pedidos por WhatsApp, inventario privado, carga XLSX/CSV, compras, ventas, dashboard y comprobantes internos. No emite documentos SUNAT ni procesa pagos en línea. No requiere cuentas de clientes.

## 1. Subir a GitHub

Extrae el ZIP y sube **el contenido** de la carpeta extraída a `guiller17-1/Yolymax` (no el ZIP ni la carpeta contenedora). `public`, `src`, `migrations`, `tests`, `wrangler.jsonc`, `package.json` y `README.md` deben quedar en la raíz. No subas contraseñas ni archivos `.dev.vars`.

## 2. Crear recursos separados de TruckFlow

* D1: `yolymax-db`, ubicación automática. Copia el Database ID y reemplaza `REEMPLAZAR_CON_DATABASE_ID` en `wrangler.jsonc`.
* R2: `yolymax-imagenes` (privado; no activar URL pública del bucket). Las imágenes iniciales se sirven como archivos estáticos, las nuevas mediante R2 y el Worker.
* Worker: `yolymax`. El nombre, DB y bucket deben ser los propios de este negocio.

## 3. Inicializar y desplegar (Windows PowerShell o terminal)

Instala Node.js 22 o posterior. En la carpeta del repositorio ejecuta:

```bash
npm install
npx wrangler login
npm run db:remote
npm run deploy
npx wrangler secret put ADMIN_PASSWORD
```

Introduce una contraseña larga y única (14 caracteres como mínimo, idealmente 24+ aleatorios). No existe contraseña predeterminada. No la escribas en GitHub ni en `wrangler.jsonc`. Puedes configurarla también desde Settings > Variables and Secrets del Worker como **Secret**. El catálogo funcionará antes de definir la contraseña, pero el inicio de sesión administrativo quedará deshabilitado. Si R2 o D1 no existen, primero créalos. No ejecutes migraciones sobre la DB de TruckFlow.

Para despliegue automático, conectar el repositorio privado en Workers & Pages > Create application > Import a repository (o Settings > Builds del Worker existente). Comando de despliegue `npm run deploy`, directorio raíz `/`, sin compilación adicional. Aplicar migraciones D1 antes del primer despliegue; no automatizar migraciones destructivas. Si se crea primero el Worker por el dashboard, conservar el mismo nombre. El servicio mostrará el enlace workers.dev real.

## 4. Prueba de aceptación antes de vender

1. Verificar `/api/health` (ok true); abrir `/` y comprobar las cinco promociones. Todos empiezan sin stock; registrar existencias reales.
2. En `/admin` ingresar la contraseña. En Importar Excel descargar plantilla, completar y revisar vista previa. SKU existente se actualiza y cantidad reemplaza stock; para sumar mercadería usar Compras. No incluir filas ilustrativas si no son reales. Se aconseja importar por lotes de hasta 300 productos; no usar fotos en el Excel.
3. Registrar compra, verificar incremento de stock. Registrar venta, verificar decremento y comprobante imprimible sin validez tributaria. Revisar historial.
4. Desde incógnito o un segundo celular, verificar que el catálogo muestra disponibilidad sin cantidades ni costos. Crear pedido y comprobar que aparece en Pedidos ANTES de abrir WhatsApp. El cliente aún debe pulsar Enviar dentro de WhatsApp.
5. Confirmar un pedido: reserva stock. Finalizar: crea venta sin descontar otra vez. Cancelar confirmado: libera stock. Un pedido pendiente no reserva unidades. Si hay conflicto entre dos dispositivos, el servidor rechaza la escritura antigua y se recargan los datos: volver a ingresar la operación.
6. Verificar `/api/admin/state` en incógnito: debe devolver 401. Cerrar sesión y repetir. Probar carga de una foto nueva.
7. Si alguna prueba falla, no usar datos reales todavía. Hacer respaldo de D1 antes de cambios de esquema. Exportar respaldo JSON desde administración, mantenerlo privado. En producción configurar además respaldo y alertas de Cloudflare.

## Arquitectura y límites de esta primera versión

`public/index.html` conserva estilos V3; `public/app.js` usa API HTTPS (carrito/favoritos pueden mantenerse en el navegador). `src/index.js` es Worker. D1 mantiene productos, pedidos, compras, ventas y movimientos en tablas independientes; cada registro guarda detalles JSON; la revisión global y batch atómico evitan que escrituras antiguas sobrescriban operaciones concurrentes. El catálogo público usa lista explícita de campos. La API privada requiere una sesión con cookie HttpOnly/Secure/SameSite y token revocable; limita intentos de acceso. La autenticación es de propietario por contraseña de servidor, **no Cloudflare Access aún**: agregar Access con dominio y políticas de identidad en la etapa de endurecimiento. No hay roles múltiples ni autenticación de clientes. Nunca confíes en ocultar el panel para proteger datos; la autorización se comprueba en API.

El flujo administrativo de esta versión sincroniza un snapshot privado con revisión, no una API paginada por entidad. Límite de envío 5 MB, máximo 800 registros modificados por guardado; dividir cargas grandes y migrar a endpoints incrementales antes de que el historial alcance esos límites. No es un sistema contable certificado. R2 puede acumular imágenes reemplazadas; no borrar objetos sin verificar referencias. Se requiere revisar política de privacidad y configurar protecciones antiabuso antes del lanzamiento público.

## Pruebas locales

`npm test` ejecuta un adaptador SQLite en memoria sobre el Worker y las migraciones (Node 22+). Verifica login, autorización, privacidad, compra, venta por pedido, reserva, concurrencia mediante revisión y validación de precio. No sustituye la prueba en el Cloudflare real. Para probar con Wrangler, configurar ID en `wrangler.jsonc`, crear `.dev.vars` desde el ejemplo, `npm install`, `npm run db:local`, `npm run dev`. Si el navegador local no acepta cookie Secure, probar en el entorno HTTPS desplegado. No se ha desplegado en tu cuenta.
