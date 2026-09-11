from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def ahora_utc():
    """
    Devuelve la fecha y hora actual en UTC
    incluyendo información de zona horaria.
    """
    return datetime.now(timezone.utc)


class StockSnapshot(db.Model):
    __tablename__ = "stock_snapshots"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    snapshot_date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    captured_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc
    )

    marca = db.Column(
        db.String(160),
        nullable=False
    )

    producto = db.Column(
        db.String(220),
        nullable=False
    )

    precio = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    stock = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    imagenes_json = db.Column(
        db.Text,
        nullable=False,
        default="[]"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_date",
            "marca",
            "producto",
            name="uq_snapshot_product"
        ),
    )


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    code = db.Column(
        db.String(40),
        unique=True,
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        index=True
    )

    customer_name = db.Column(
        db.String(160),
        nullable=False
    )

    customer_phone = db.Column(
        db.String(20),
        nullable=False
    )

    total = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Pendiente",
        index=True
    )

    channel = db.Column(
        db.String(30),
        nullable=False,
        default="WhatsApp"
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc
    )

    lines = db.relationship(
        "OrderLine",
        backref="order",
        lazy=True,
        cascade="all, delete-orphan"
    )


class OrderLine(db.Model):
    __tablename__ = "order_lines"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True
    )

    marca = db.Column(
        db.String(160),
        nullable=False
    )

    producto = db.Column(
        db.String(220),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    unit_price = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    subtotal = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )
