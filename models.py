from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class StockSnapshot(db.Model):
    __tablename__ = 'stock_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    product_id = db.Column(db.String(50), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    customer_name = db.Column(db.String(150), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pendiente')  # Pendiente, Confirmado, Rechazado
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lines = db.relationship('OrderLine', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderLine(db.Model):
    __tablename__ = 'order_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
