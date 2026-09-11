def calculate_product_stock():
    """Calcula el stock disponible considerando reservas sin exponerlo públicamente"""
    products = load_local_inventory()
    stock_map, latest_date = get_latest_stock_snapshots()
    
    reserved_query = db.session.query(
        OrderLine.product_id,
        db.func.sum(OrderLine.quantity).label('total_reserved')
    ).join(Order).filter(Order.status.in_(['Pendiente', 'Confirmado']))
    
    if latest_date:
        reserved_query = reserved_query.filter(db.func.date(Order.created_at) >= latest_date)
        
    reserved_map = dict(reserved_query.group_by(OrderLine.product_id).all())
    
    result = []
    for p in products:
        p_id = str(p['id'])
        base_stock = stock_map.get(p_id, p.get('stock', 0))
        reserved = reserved_map.get(p_id, 0)
        available = max(0, base_stock - reserved)
        
        # Soporte para múltiples imágenes o imagen única
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
            "stock_base": base_stock,
            "reservado": reserved,
            "stock_disponible": available
        })
    return result
