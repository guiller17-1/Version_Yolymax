import os
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuración de Clave Secreta
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secreto-yolymax-2026')

# Configuración de Base de Datos (PostgreSQL o SQLite local)
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///local_yolymax.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DE BASE DE DATOS ---
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pendiente') # Pendiente, Confirmado, Cancelado
    total = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lines = db.relationship('OrderLine', backref='order', lazy=True)

class OrderLine(db.Model):
    __tablename__ = 'order_lines'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.String(50), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class StockSnapshot(db.Model):
    __tablename__ = 'stock_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), nullable=False)
    base_stock = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- FUNCIONES AUXILIARES ---
def load_local_inventory():
    filename = 'inventory.json'
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error al leer {filename}: {e}")
    return []

def get_latest_stock_snapshots():
    snapshots = StockSnapshot.query.all()
    stock_map = {}
    latest_date = None
    for s in snapshots:
        stock_map[str(s.product_id)] = s.base_stock
        if not latest_date or s.updated_at > latest_date:
            latest_date = s.updated_at
    return stock_map, latest_date

def calculate_product_stock():
    """Calcula el stock disponible sin mostrar cantidades al cliente público"""
    products = load_local_inventory()
    stock_map, latest_date = get_latest_stock_snapshots()
    
    reserved_map = {}
    if Order.query.first():
        query = db.session.query(
            OrderLine.product_id,
            db.func.sum(OrderLine.quantity).label('total_reserved')
        ).join(Order).filter(Order.status.in_(['Pendiente', 'Confirmado']))
        
        if latest_date:
            query = query.filter(Order.created_at >= latest_date)
            
        reserved_map = dict(query.group_by(OrderLine.product_id).all())

    result = []
    for p in products:
        p_id = str(p.get('id', ''))
        base_stock = stock_map.get(p_id, p.get('stock', 0))
        reserved = reserved_map.get(p_id, 0)
        available = max(0, base_stock - reserved)
        
        # Soporte para varias imagenes o una sola
        imgs = p.get('imagenes', [])
        if not imgs and p.get('imagen'):
            imgs = [p.get('imagen')]
            
        result.append({
            "id": p_id,
            "nombre": p.get('nombre', ''),
            "descripcion": p.get('descripcion', ''),
            "precio": float(p.get('precio', 0.0)),
            "imagen": p.get('imagen', ''),
            "imagenes": imgs,
            "stock_disponible": available
        })
    return result

# --- RUTAS DE LA APLICACIÓN ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/productos')
def get_productos():
    productos = calculate_product_stock()
    return jsonify(productos)

@app.route('/api/pedidos', methods=['POST'])
def create_order():
    data = request.json or {}
    nombre = data.get('nombre')
    telefono = data.get('telefono')
    items = data.get('items', [])
    
    if not nombre or not telefono or not items:
        return jsonify({"error": "Por favor completa todos los campos obligatorios."}), 400
        
    productos = {p['id']: p for p in calculate_product_stock()}
    
    total = 0.0
    lines_to_create = []
    
    for item in items:
        p_id = str(item.get('product_id'))
        qty = int(item.get('quantity', 0))
        if p_id not in productos:
            return jsonify({"error": "Producto no encontrado."}), 400
        prod = productos[p_id]
        if qty > prod['stock_disponible']:
            return jsonify({"error": f"Sin stock disponible suficiente para {prod['nombre']}."}), 400
        
        subtotal = prod['precio'] * qty
        total += subtotal
        lines_to_create.append(OrderLine(
            product_id=p_id,
            product_name=prod['nombre'],
            unit_price=prod['precio'],
            quantity=qty
        ))
        
    code = f"PED-{int(datetime.utcnow().timestamp())}"
    order = Order(code=code, customer_name=nombre, customer_phone=telefono, total=total, lines=lines_to_create)
    db.session.add(order)
    db.session.commit()
    
    return jsonify({"status": "exito", "codigo": code})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
