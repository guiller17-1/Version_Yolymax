import io
import json
import os
import re
import secrets
from datetime import datetime, time as dt_time, timezone
from decimal import Decimal
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook, load_workbook
from sqlalchemy import func

from models import Order, OrderLine, StockSnapshot, db


# =========================================================
# ZONAS HORARIAS
# =========================================================

LIMA = ZoneInfo("America/Lima")
UTC = timezone.utc


# =========================================================
# CONFIGURACIÓN DE FLASK
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    secrets.token_hex(32)
)

database_url = os.getenv(
    "DATABASE_URL",
    "sqlite:///pedidos.db"
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


ONEDRIVE_URL = os.getenv(
    "ONEDRIVE_URL",
    ""
).strip()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    ""
).strip()

CRON_SECRET = os.getenv(
    "CRON_SECRET",
    ""
).strip()


# =========================================================
# UTILIDADES DE FECHA Y HORA
# =========================================================

def ahora_utc():
    return datetime.now(UTC)


def ahora_lima():
    return datetime.now(LIMA)


def asegurar_utc(fecha):
    if fecha is None:
        return None

    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=UTC)

    return fecha.astimezone(UTC)


def convertir_a_hora_peru(fecha):
    fecha_utc = asegurar_utc(fecha)

    if fecha_utc is None:
        return None

    return fecha_utc.astimezone(LIMA)


@app.template_filter("hora_peru")
def filtro_hora_peru(fecha):
    fecha_peru = convertir_a_hora_peru(fecha)

    if fecha_peru is None:
        return ""

    return fecha_peru.strftime(
        "%d/%m/%Y %I:%M:%S %p"
    )


@app.template_filter("fecha_peru")
def filtro_fecha_peru(fecha):
    fecha_peru = convertir_a_hora_peru(fecha)

    if fecha_peru is None:
        return ""

    return fecha_peru.strftime("%d/%m/%Y")


@app.template_filter("hora_peru_corta")
def filtro_hora_peru_corta(fecha):
    fecha_peru = convertir_a_hora_peru(fecha)

    if fecha_peru is None:
        return ""

    return fecha_peru.strftime("%I:%M:%S %p")


# =========================================================
# UTILIDADES GENERALES
# =========================================================

def normalizar(texto):
    return str(texto or "").strip().casefold()


def entero_stock(valor):
    try:
        return max(
            0,
            int(float(valor or 0))
        )
    except (TypeError, ValueError):
        return 0


def estado(stock):
    if stock >= 3:
        return "Disponible"

    if stock >= 1:
        return "Ultimas unidades"

    return "No disponible"


# =========================================================
# DESCARGA DEL EXCEL DE ONEDRIVE
# =========================================================

def download_onedrive():
    if not ONEDRIVE_URL:
        raise RuntimeError(
            "ONEDRIVE_URL no configurada"
        )

    candidates = [ONEDRIVE_URL]

    separator = (
        "&"
        if "?" in ONEDRIVE_URL
        else "?"
    )

    candidates.append(
        ONEDRIVE_URL + separator + "download=1"
    )

    last_error = None

    for url in candidates:
        try:
            response = requests.get(
                url,
                timeout=30,
                allow_redirects=True
            )

            response.raise_for_status()

            if response.content[:2] == b"PK":
                return response.content

            last_error = ValueError(
                "OneDrive devolvió una página "
                "y no el archivo Excel"
            )

        except Exception as error:
            last_error = error

    raise last_error or RuntimeError(
        "No se pudo descargar el Excel"
    )


# =========================================================
# LECTURA DEL EXCEL
# =========================================================

def parse_excel(content):
    workbook = load_workbook(
        io.BytesIO(content),
        data_only=True,
        read_only=True,
        keep_vba=True
    )

    if "Inventario" not in workbook.sheetnames:
        raise ValueError(
            "No existe la hoja Inventario"
        )

    worksheet = workbook["Inventario"]

    rows = worksheet.iter_rows(
        values_only=True
    )

    first = next(rows, None)

    if first is None:
        raise ValueError(
            "La hoja Inventario está vacía"
        )

    headers = {
        str(value).strip(): index
        for index, value in enumerate(first)
        if value is not None
    }

    required = (
        "Marca",
        "Producto",
        "Stock Actual",
        "Precio",
        "Imagen 1",
        "Imagen 2",
        "Imagen 3"
    )

    for column in required:
        if column not in headers:
            raise ValueError(
                f"No existe la columna {column}"
            )

    items = []

    for row in rows:
        marca = row[headers["Marca"]]
        producto = row[headers["Producto"]]

        if not marca or not producto:
            continue

        imagenes = []

        for column in (
            "Imagen 1",
            "Imagen 2",
            "Imagen 3"
        ):
            value = str(
                row[headers[column]] or ""
            ).strip()

            if value:
                imagenes.append(value)

        try:
            precio = Decimal(
                str(
                    row[headers["Precio"]] or 0
                )
            )
        except Exception:
            precio = Decimal("0")

        items.append({
            "marca": str(marca).strip(),
            "producto": str(producto).strip(),
            "precio": precio,
            "stock": entero_stock(
                row[headers["Stock Actual"]]
            ),
            "imagenes": imagenes,
        })

    return items


# =========================================================
# INVENTARIO DE RESPALDO
# =========================================================

def load_fallback():
    file_path = Path("inventory.json")

    if not file_path.exists():
        return []

    try:
        with file_path.open(
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        items = []

        for row in data:
            marca = str(
                row.get("marca", "")
            ).strip()

            producto = str(
                row.get("producto", "")
            ).strip()

            if not marca or not producto:
                continue

            try:
                precio = Decimal(
                    str(
                        row.get("precio", 0)
                    )
                )
            except Exception:
                precio = Decimal("0")

            imagenes = [
                str(img).strip()
                for img in row.get("imagenes", [])
                if str(img).strip()
            ]

            items.append({
                "marca": marca,
                "producto": producto,
                "precio": precio,
                "stock": entero_stock(
                    row.get("stock", 0)
                ),
                "imagenes": imagenes,
            })

        return items

    except Exception:
        return []


# =========================================================
# LÓGICA DE SNAPSHOTS
# =========================================================

def snapshot_date_in_use():
    now_lima = ahora_lima()

    if now_lima.time() < dt_time(6, 0):
        used_dt = now_lima.date()
        from datetime import timedelta
        return used_dt - timedelta(days=1)

    return now_lima.date()


def create_daily_snapshot(force=False):
    target_date = snapshot_date_in_use()

    existing = StockSnapshot.query.filter_by(
        snapshot_date=target_date
    ).first()

    if existing and not force:
        return {
            "creado": False,
            "motivo": "Ya existe foto para hoy",
            "fecha": target_date.isoformat(),
        }

    items = []

    try:
        content = download_onedrive()
        items = parse_excel(content)
    except Exception as exc:
        app.logger.warning(
            "Error obteniendo Excel de OneDrive: %s",
            exc
        )
        items = load_fallback()

    if not items:
        return {
            "creado": False,
            "motivo": "No se obtuvieron productos",
            "fecha": target_date.isoformat(),
        }

    if existing and force:
        StockSnapshot.query.filter_by(
            snapshot_date=target_date
        ).delete()

    new_objects = []

    for item in items:
        new_objects.append(
            StockSnapshot(
                snapshot_date=target_date,
                captured_at=ahora_utc(),
                marca=item["marca"],
                producto=item["producto"],
                precio=item["precio"],
                stock=item["stock"],
                imagenes_json=json.dumps(
                    item["imagenes"],
                    ensure_ascii=False
                ),
            )
        )

    db.session.add_all(new_objects)
    db.session.commit()

    return {
        "creado": True,
        "registros": len(new_objects),
        "fecha": target_date.isoformat(),
    }


def ensure_snapshot():
    target_date = snapshot_date_in_use()

    count = StockSnapshot.query.filter_by(
        snapshot_date=target_date
    ).count()

    if count == 0:
        create_daily_snapshot(force=False)


def obtener_primera_captura(date_used):
    if date_used is None:
        return None

    return (
        db.session.query(
            func.min(StockSnapshot.captured_at)
        )
        .filter(
            StockSnapshot.snapshot_date == date_used
        )
        .scalar()
    )


def reserved_quantities():
    date_used = snapshot_date_in_use()
    captured_at_start = obtener_primera_captura(date_used)

    if captured_at_start is None:
        captured_at_start = ahora_utc()

    rows = (
        db.session.query(
            OrderLine.marca,
            OrderLine.producto,
            func.sum(OrderLine.quantity)
        )
        .join(Order)
        .filter(
            Order.created_at >= captured_at_start,
            Order.status == "Pendiente"
        )
        .group_by(
            OrderLine.marca,
            OrderLine.producto
        )
        .all()
    )

    result = {}

    for marca, producto, qty in rows:
        key = (
            normalizar(marca),
            normalizar(producto)
        )
        result[key] = int(qty or 0)

    return result


def catalog_items():
    ensure_snapshot()
    date_used = snapshot_date_in_use()

    snapshots = (
        StockSnapshot.query
        .filter_by(snapshot_date=date_used)
        .order_by(
            StockSnapshot.marca.asc(),
            StockSnapshot.producto.asc()
        )
        .all()
    )

    reservas = reserved_quantities()
    catalog = []

    for item in snapshots:
        key = (
            normalizar(item.marca),
            normalizar(item.producto)
        )

        cant_reservada = reservas.get(key, 0)
        stock_disp = max(
            0,
            item.stock - cant_reservada
        )

        try:
            imagenes = json.loads(
                item.imagenes_json or "[]"
            )
        except Exception:
            imagenes = []

        catalog.append({
            "marca": item.marca,
            "producto": item.producto,
            "precio": float(item.precio),
            "stock": stock_disp,
            "estado": estado(stock_disp),
            "imagenes": imagenes,
        })

    return catalog


def find_snapshot(marca, producto):
    date_used = snapshot_date_in_use()

    return StockSnapshot.query.filter(
        StockSnapshot.snapshot_date == date_used,
        func.lower(StockSnapshot.marca) == normalizar(marca),
        func.lower(StockSnapshot.producto) == normalizar(producto)
    ).first()


def available_stock(snapshot):
    if not snapshot:
        return 0

    reservas = reserved_quantities()
    key = (
        normalizar(snapshot.marca),
        normalizar(snapshot.producto)
    )

    cant_reservada = reservas.get(key, 0)

    return max(
        0,
        snapshot.stock - cant_reservada
    )


# =========================================================
# AUTENTICACIÓN ADMIN
# =========================================================

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(
                url_for("admin_login")
            )
        return view(*args, **kwargs)

    return wrapped


def initialize_database():
    with app.app_context():
        db.create_all()


# =========================================================
# RUTAS PÚBLICAS
# =========================================================

@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/productos")
def productos():
    return jsonify(catalog_items())


@app.post("/api/verificar-disponibilidad")
def verificar_disponibilidad():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])

    if not items:
        return jsonify({
            "valido": False,
            "mensaje": "Carrito vacío"
        }), 400

    ensure_snapshot()

    for item in items:
        marca = str(item.get("marca", "")).strip()
        producto = str(item.get("producto", "")).strip()
        cant = entero_stock(item.get("cantidad", 1))

        snap = find_snapshot(marca, producto)

        if not snap:
            return jsonify({
                "valido": False,
                "mensaje": f"El producto {marca} - {producto} ya no existe"
            }), 400

        disp = available_stock(snap)

        if cant > disp:
            return jsonify({
                "valido": False,
                "mensaje": f"Stock insuficiente para {marca} - {producto}. Disponibles: {disp}"
            }), 400

    return jsonify({"valido": True})


@app.post("/api/pedidos")
def crear_pedido():
    data = request.get_json(silent=True) or {}

    nombre = str(data.get("cliente_nombre", "")).strip()
    telefono = str(data.get("cliente_telefono", "")).strip()
    items = data.get("items", [])

    if not nombre or not telefono or not items:
        return jsonify({
            "ok": False,
            "mensaje": "Datos incompletos"
        }), 400

    ensure_snapshot()

    lines_to_create = []
    total_pedido = Decimal("0")

    for item in items:
        marca = str(item.get("marca", "")).strip()
        producto = str(item.get("producto", "")).strip()
        cant = entero_stock(item.get("cantidad", 1))

        snap = find_snapshot(marca, producto)

        if not snap:
            return jsonify({
                "ok": False,
                "mensaje": f"Producto no disponible: {marca} - {producto}"
            }), 400

        disp = available_stock(snap)

        if cant > disp:
            return jsonify({
                "ok": False,
                "mensaje": f"No hay stock suficiente de {marca} - {producto}"
            }), 400

        subtotal = snap.precio * cant
        total_pedido += subtotal

        lines_to_create.append({
            "marca": snap.marca,
            "producto": snap.producto,
            "quantity": cant,
            "unit_price": snap.precio,
            "subtotal": subtotal,
        })

    code = "PED-" + ahora_lima().strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()

    order = Order(
        code=code,
        customer_name=nombre,
        customer_phone=telefono,
        total=total_pedido,
        status="Pendiente",
        channel="WhatsApp",
        created_at=ahora_utc(),
        updated_at=ahora_utc(),
    )

    db.session.add(order)
    db.session.flush()

    for line in lines_to_create:
        db.session.add(
            OrderLine(
                order_id=order.id,
                marca=line["marca"],
                producto=line["producto"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                subtotal=line["subtotal"],
            )
        )

    db.session.commit()

    return jsonify({
        "ok": True,
        "codigo": order.code,
        "total": float(order.total)
    })


# =========================================================
# RUTAS DE ADMINISTRACIÓN
# =========================================================

@app.get("/admin/login")
def admin_login():
    return render_template(
        "admin_login.html",
        error=None
    )


@app.post("/admin/login")
def admin_login_post():
    password = request.form.get(
        "password",
        ""
    )

    if (
        not ADMIN_PASSWORD
        or not secrets.compare_digest(
            password,
            ADMIN_PASSWORD
        )
    ):
        return render_template(
            "admin_login.html",
            error="Contraseña incorrecta"
        ), 401

    session.clear()
    session["admin"] = True

    return redirect(
        url_for("admin_orders")
    )


@app.post("/admin/logout")
def admin_logout():
    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# PANEL DE PEDIDOS Y GESTIÓN DE STOCK
# =========================================================

@app.get("/admin/pedidos")
@admin_required
def admin_orders():
    orders = (
        Order.query
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    return render_template(
        "admin_orders.html",
        orders=orders
    )


# =========================================================
# GESTIÓN DE VENTAS Y ENTRADAS EN EXCEL Y STOCK REAL
# =========================================================

def registrar_venta_excel(order):
    excel_path = Path("Productos_Julio.xlsx")
    
    if excel_path.exists():
        workbook = load_workbook(excel_path)
    else:
        workbook = Workbook()

    if "Ventas" in workbook.sheetnames:
        worksheet = workbook["Ventas"]
    else:
        worksheet = workbook.create_sheet("Ventas")
        worksheet.append([
            "Fecha Perú", "Código Pedido", "Marca", "Producto",
            "Cantidad", "Precio Unitario", "Subtotal", "Cliente"
        ])

    created_peru = convertir_a_hora_peru(order.created_at)
    fecha_str = created_peru.strftime("%d/%m/%Y %I:%M %p") if created_peru else ""
    cliente_str = f"{order.customer_name} ({order.customer_phone})"

    for line in order.lines:
        worksheet.append([
            fecha_str,
            order.code,
            line.marca,
            line.producto,
            line.quantity,
            float(line.unit_price),
            float(line.subtotal),
            cliente_str
        ])

    workbook.save(excel_path)


@app.get("/admin/stock")
@admin_required
def admin_stock():
    date_used = snapshot_date_in_use()
    snapshots = (
        StockSnapshot.query
        .filter_by(snapshot_date=date_used)
        .order_by(StockSnapshot.marca.asc(), StockSnapshot.producto.asc())
        .all()
    ) if date_used else []

    reservas = reserved_quantities()
    reporte = []

    for item in snapshots:
        key = (normalizar(item.marca), normalizar(item.producto))
        cant_reservada = reservas.get(key, 0)
        disponible_real = max(0, item.stock - cant_reservada)

        reporte.append({
            "marca": item.marca,
            "producto": item.producto,
            "stock_base": item.stock,
            "reservado": cant_reservada,
            "disponible_real": disponible_real
        })

    return render_template("admin_stock.html", reporte=reporte)


@app.post("/admin/entradas/guardar")
@admin_required
def registrar_entrada():
    marca = request.form.get("marca", "").strip()
    producto = request.form.get("producto", "").strip()
    cantidad = entero_stock(request.form.get("cantidad", 0))
    nota = request.form.get("nota", "").strip()

    if marca and producto and cantidad > 0:
        excel_path = Path("Productos_Julio.xlsx")
        workbook = load_workbook(excel_path) if excel_path.exists() else Workbook()
        worksheet = workbook["Entradas"] if "Entradas" in workbook.sheetnames else workbook.create_sheet("Entradas")

        if worksheet.max_row == 1 and worksheet.cell(1, 1).value is None:
            worksheet.append(["Fecha Perú", "Marca", "Producto", "Cantidad Ingresada", "Nota / Proveedor"])

        worksheet.append([
            ahora_lima().strftime("%d/%m/%Y %I:%M %p"),
            marca,
            producto,
            cantidad,
            nota
        ])
        workbook.save(excel_path)

    return redirect(url_for("admin_stock"))


@app.post(
    "/admin/pedidos/<int:order_id>/estado"
)
@admin_required
def update_order_status(order_id):
    order = db.session.get(
        Order,
        order_id
    )

    if order is None:
        return jsonify({
            "ok": False,
            "mensaje": "Pedido no encontrado"
        }), 404

    new_status = str(
        (
            request.get_json(
                silent=True
            ) or {}
        ).get("estado", "")
    ).strip()

    valid_statuses = {
        "Pendiente",
        "Confirmado",
        "Rechazado"
    }

    if new_status not in valid_statuses:
        return jsonify({
            "ok": False,
            "mensaje": "Estado inválido"
        }), 400

    if new_status == "Confirmado" and order.status != "Confirmado":
        registrar_venta_excel(order)

    order.status = new_status
    order.updated_at = ahora_utc()

    db.session.commit()

    return jsonify({
        "ok": True,
        "estado": order.status,
        "actualizado_peru": filtro_hora_peru(
            order.updated_at
        ),
    })


# =========================================================
# EXPORTACIÓN A EXCEL
# =========================================================

@app.get("/admin/exportar-pedidos.xlsx")
@admin_required
def export_orders():
    workbook = Workbook()

    orders_sheet = workbook.active
    orders_sheet.title = "Pedidos"

    orders_sheet.append([
        "Código",
        "Fecha Perú",
        "Hora Perú",
        "Cliente",
        "Celular",
        "Total",
        "Estado",
        "Canal",
        "Última actualización Perú",
    ])

    details_sheet = workbook.create_sheet(
        "DetallePedidos"
    )

    details_sheet.append([
        "Código",
        "Fecha Perú",
        "Hora Perú",
        "Marca",
        "Producto",
        "Cantidad",
        "Precio unitario",
        "Subtotal",
        "Estado",
    ])

    orders = (
        Order.query
        .order_by(
            Order.created_at.asc()
        )
        .all()
    )

    for order in orders:
        created_peru = convertir_a_hora_peru(
            order.created_at
        )

        updated_peru = convertir_a_hora_peru(
            order.updated_at
        )

        orders_sheet.append([
            order.code,
            (
                created_peru.strftime("%d/%m/%Y")
                if created_peru
                else ""
            ),
            (
                created_peru.strftime("%I:%M:%S %p")
                if created_peru
                else ""
            ),
            order.customer_name,
            order.customer_phone,
            float(order.total),
            order.status,
            order.channel,
            (
                updated_peru.strftime(
                    "%d/%m/%Y %I:%M:%S %p"
                )
                if updated_peru
                else ""
            ),
        ])

        for line in order.lines:
            details_sheet.append([
                order.code,
                (
                    created_peru.strftime("%d/%m/%Y")
                    if created_peru
                    else ""
                ),
                (
                    created_peru.strftime("%I:%M:%S %p")
                    if created_peru
                    else ""
                ),
                line.marca,
                line.producto,
                line.quantity,
                float(line.unit_price),
                float(line.subtotal),
                order.status,
            ])

    snapshots_sheet = workbook.create_sheet(
        "StockDiario"
    )

    snapshots_sheet.append([
        "Fecha de stock",
        "Fecha de captura Perú",
        "Hora de captura Perú",
        "Marca",
        "Producto",
        "Precio",
        "Stock base",
    ])

    snapshots = (
        StockSnapshot.query
        .order_by(
            StockSnapshot.snapshot_date.asc(),
            StockSnapshot.marca.asc(),
            StockSnapshot.producto.asc(),
        )
        .all()
    )

    for snapshot in snapshots:
        captured_peru = convertir_a_hora_peru(
            snapshot.captured_at
        )

        snapshots_sheet.append([
            snapshot.snapshot_date.strftime(
                "%d/%m/%Y"
            ),
            (
                captured_peru.strftime("%d/%m/%Y")
                if captured_peru
                else ""
            ),
            (
                captured_peru.strftime("%I:%M:%S %p")
                if captured_peru
                else ""
            ),
            snapshot.marca,
            snapshot.producto,
            float(snapshot.precio),
            snapshot.stock,
        ])

    for worksheet in workbook.worksheets:
        for column_cells in worksheet.columns:
            max_length = 0

            column_letter = (
                column_cells[0].column_letter
            )

            for cell in column_cells:
                value_length = len(
                    str(cell.value or "")
                )

                if value_length > max_length:
                    max_length = value_length

            worksheet.column_dimensions[
                column_letter
            ].width = min(
                max_length + 2,
                45
            )

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = (
            worksheet.dimensions
        )

    output = io.BytesIO()

    workbook.save(output)
    output.seek(0)

    filename = (
        "pedidos_"
        f"{ahora_lima().strftime('%Y%m%d_%H%M')}"
        ".xlsx"
    )

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


# =========================================================
# TAREA DIARIA DE LAS 6:00 A. M. DE PERÚ
# =========================================================

@app.post("/api/tareas/captura-diaria")
def daily_snapshot_task():
    supplied = request.headers.get(
        "X-Cron-Secret",
        ""
    )

    if (
        not CRON_SECRET
        or not secrets.compare_digest(
            supplied,
            CRON_SECRET
        )
    ):
        return jsonify({
            "ok": False
        }), 403

    try:
        result = create_daily_snapshot(
            force=False
        )

        return jsonify({
            "ok": True,
            "hora_peru": ahora_lima().strftime(
                "%d/%m/%Y %I:%M:%S %p"
            ),
            **result
        })

    except Exception as error:
        app.logger.exception(
            "Fallo de captura diaria: %s",
            error
        )

        return jsonify({
            "ok": False,
            "mensaje": str(error),
            "hora_peru": ahora_lima().strftime(
                "%d/%m/%Y %I:%M:%S %p"
            ),
        }), 500


# =========================================================
# ESTADO DEL SERVICIO
# =========================================================

@app.get("/health")
def health():
    return {
        "ok": True,
        "zona_horaria": "America/Lima",
        "fecha_hora_peru": ahora_lima().strftime(
            "%d/%m/%Y %I:%M:%S %p"
        ),
        "fecha_hora_utc": ahora_utc().isoformat(),
    }


# =========================================================
# CREACIÓN INICIAL DE TABLAS
# =========================================================

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv("PORT", "5000")
        ),
        debug=True
    )
