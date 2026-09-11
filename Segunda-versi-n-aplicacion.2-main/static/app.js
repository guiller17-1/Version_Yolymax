let catalogo = [];
let productoActual = null;
let imagenes = [];
let imagenIndice = 0;
let cesta = JSON.parse(localStorage.getItem('pedido_perfumes') || '[]');

const $ = (id) => document.getElementById(id);
const normalizar = (v) => String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
const dinero = (v) => `S/ ${Number(v || 0).toFixed(2)}`;
const clave = (x) => `${normalizar(x.marca)}|${normalizar(x.producto)}`;
const cantidadValida = (v) => Math.min(99, Math.max(1, parseInt(v, 10) || 1));

function opciones(input, box, valores, elegir) {
  const q = normalizar(input.value);
  const encontrados = [...new Set(valores)].filter(v => normalizar(v).includes(q)).slice(0, 30);
  box.innerHTML = '';
  encontrados.forEach(v => {
    const div = document.createElement('div');
    div.className = 'option';
    div.textContent = v;
    div.onclick = () => { input.value = v; box.classList.remove('open'); elegir(v); };
    box.appendChild(div);
  });
  box.classList.toggle('open', encontrados.length > 0);
}

function productosMarca() {
  const marca = normalizar($('marca').value);
  return catalogo.filter(x => !marca || normalizar(x.marca) === marca).map(x => x.producto);
}

function mensaje(id, texto, tipo='ok') {
  const el = $(id);
  el.textContent = texto;
  el.className = `message ${tipo}`;
}
function ocultarMensaje(id) { $(id).className = 'message hidden'; $(id).textContent = ''; }

function mostrarImagen() {
  const img = $('imagen-producto');
  if (!imagenes.length) { img.classList.add('hidden'); return; }
  img.src = imagenes[imagenIndice];
  img.classList.remove('hidden');
  img.onerror = () => img.classList.add('hidden');
  $('imagen-anterior').classList.toggle('hidden', imagenes.length < 2);
  $('imagen-siguiente').classList.toggle('hidden', imagenes.length < 2);
  $('indicadores-imagen').innerHTML = imagenes.map((_, i) => `<button class="${i === imagenIndice ? 'active' : ''}" data-i="${i}"></button>`).join('');
  $('indicadores-imagen').querySelectorAll('button').forEach(b => b.onclick = () => { imagenIndice = Number(b.dataset.i); mostrarImagen(); });
}

$('imagen-anterior').onclick = () => { imagenIndice = (imagenIndice - 1 + imagenes.length) % imagenes.length; mostrarImagen(); };
$('imagen-siguiente').onclick = () => { imagenIndice = (imagenIndice + 1) % imagenes.length; mostrarImagen(); };

function seleccionarProducto(nombre) {
  const marca = normalizar($('marca').value);
  productoActual = catalogo.find(x => normalizar(x.producto) === normalizar(nombre) && (!marca || normalizar(x.marca) === marca));
  if (!productoActual) return;
  $('marca').value = productoActual.marca;
  $('producto').value = productoActual.producto;
  $('nombre-producto').textContent = productoActual.producto;
  $('marca-producto').textContent = productoActual.marca;
  $('precio').textContent = dinero(productoActual.precio);
  $('cantidad-producto').value = 1;
  imagenes = productoActual.imagenes || [];
  imagenIndice = 0;
  mostrarImagen();
  const estado = normalizar(productoActual.estado);
  const result = $('resultado');
  result.className = 'status';
  if (estado.includes('ultima')) {
    result.classList.add('warning'); $('estado').textContent = 'Últimas unidades'; $('mensaje-estado').textContent = '¡No te quedes sin el tuyo!';
  } else if (estado === 'disponible') {
    result.classList.add('available'); $('estado').textContent = 'Disponible'; $('mensaje-estado').textContent = 'Producto disponible para entrega.';
  } else {
    result.classList.add('danger'); $('estado').textContent = 'No disponible'; $('mensaje-estado').textContent = 'Producto agotado por el momento.';
  }
  const noDisponible = estado === 'no disponible';
  $('agregar-pedido').disabled = noDisponible;
  $('seccion-cantidad').classList.toggle('disabled', noDisponible);
  $('ficha-producto').classList.remove('hidden');
  ocultarMensaje('mensaje-pedido');
}

$('marca').oninput = () => { opciones($('marca'), $('marcas'), catalogo.map(x => x.marca), () => { $('producto').value=''; }); $('producto').value=''; $('ficha-producto').classList.add('hidden'); };
$('marca').onfocus = $('marca').oninput;
$('producto').oninput = () => { opciones($('producto'), $('productos'), productosMarca(), seleccionarProducto); $('ficha-producto').classList.add('hidden'); };
$('producto').onfocus = () => opciones($('producto'), $('productos'), productosMarca(), seleccionarProducto);
document.addEventListener('click', e => { if (!e.target.closest('.combo')) document.querySelectorAll('.options').forEach(x => x.classList.remove('open')); });

$('disminuir-cantidad').onclick = () => $('cantidad-producto').value = Math.max(1, cantidadValida($('cantidad-producto').value) - 1);
$('aumentar-cantidad').onclick = () => $('cantidad-producto').value = Math.min(99, cantidadValida($('cantidad-producto').value) + 1);

async function validar(item, cantidad, enCesta=0) {
  const r = await fetch('/api/verificar-disponibilidad', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({marca:item.marca, producto:item.producto, cantidad, cantidad_en_cesta:enCesta})});
  const j = await r.json();
  if (!r.ok) throw new Error(j.mensaje || 'No se pudo validar');
  return j;
}

$('agregar-pedido').onclick = async () => {
  if (!productoActual) return;
  const cantidad = cantidadValida($('cantidad-producto').value);
  const existente = cesta.find(x => clave(x) === clave(productoActual));
  const boton = $('agregar-pedido');
  boton.disabled = true; boton.textContent = 'Verificando...';
  try {
    const res = await validar(productoActual, cantidad, existente ? existente.cantidad : 0);
    if (!res.disponible) return mensaje('mensaje-pedido', res.mensaje, 'error');
    if (existente) existente.cantidad += cantidad;
    else cesta.push({marca:productoActual.marca, producto:productoActual.producto, precio:Number(productoActual.precio), cantidad, imagen:(productoActual.imagenes || [])[0] || ''});
    guardarCesta(); renderCesta(); mensaje('mensaje-pedido', 'Producto agregado al pedido.');
  } catch (e) { mensaje('mensaje-pedido', e.message, 'error'); }
  finally { boton.disabled = false; boton.textContent = 'Agregar al pedido'; }
};

function guardarCesta() { localStorage.setItem('pedido_perfumes', JSON.stringify(cesta)); }
function renderCesta() {
  $('contador-cesta').textContent = cesta.reduce((a,x) => a + x.cantidad, 0);
  $('cesta-vacia').classList.toggle('hidden', cesta.length > 0);
  $('resumen-cesta').classList.toggle('hidden', cesta.length === 0);
  const lista = $('lista-cesta'); lista.innerHTML = '';
  cesta.forEach((item, i) => {
    const card = document.createElement('article'); card.className = 'cart-item';
    const img = document.createElement(item.imagen ? 'img' : 'div');
    img.className = 'cart-img';
    if (item.imagen) { img.src = item.imagen; img.alt = item.producto; img.onerror = () => { img.removeAttribute('src'); img.textContent='🛍️'; }; } else img.textContent='🛍️';
    const info = document.createElement('div'); info.className='cart-info';
    const title=document.createElement('h3'); title.textContent=item.producto;
    const meta=document.createElement('p'); meta.textContent=`${item.marca} · ${dinero(item.precio)} por unidad`;
    const controls=document.createElement('div'); controls.className='cart-controls';
    const minus=document.createElement('button'); minus.textContent='−'; minus.onclick=()=>{ if(item.cantidad===1)cesta.splice(i,1);else item.cantidad--; guardarCesta();renderCesta(); };
    const count=document.createElement('span'); count.textContent=item.cantidad;
    const plus=document.createElement('button'); plus.textContent='+'; plus.onclick=async()=>{ const res=await validar(item,item.cantidad+1,0); if(res.disponible){item.cantidad++;guardarCesta();renderCesta();}else mensaje('mensaje-cesta',res.mensaje,'error'); };
    const remove=document.createElement('button'); remove.className='remove'; remove.textContent='Eliminar'; remove.onclick=()=>{cesta.splice(i,1);guardarCesta();renderCesta();};
    controls.append(minus,count,plus,remove); info.append(title,meta,controls);
    const subtotal=document.createElement('strong'); subtotal.className='subtotal'; subtotal.textContent=dinero(item.precio*item.cantidad);
    card.append(img,info,subtotal); lista.appendChild(card);
  });
  $('total-cesta').textContent = dinero(cesta.reduce((a,x)=>a+x.precio*x.cantidad,0));
}

function abrirCesta(){ $('panel-cesta').classList.add('open'); $('fondo-cesta').classList.remove('hidden'); }
function cerrarCesta(){ $('panel-cesta').classList.remove('open'); $('fondo-cesta').classList.add('hidden'); }
$('abrir-cesta').onclick=abrirCesta; $('cerrar-cesta').onclick=cerrarCesta; $('fondo-cesta').onclick=cerrarCesta;
$('vaciar-cesta').onclick=()=>{cesta=[];guardarCesta();renderCesta();};
$('limpiar').onclick=()=>{$('marca').value='';$('producto').value='';$('ficha-producto').classList.add('hidden');};

$('enviar-whatsapp').onclick=()=>{ if(!cesta.length)return; $('modal-cliente').classList.remove('hidden'); };
$('cerrar-modal').onclick=()=>$('modal-cliente').classList.add('hidden');

$('form-cliente').onsubmit = async (e) => {
  e.preventDefault();
  const boton=$('confirmar-pedido'); boton.disabled=true; boton.textContent='Registrando...';
  try {
    const r=await fetch('/api/pedidos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nombre:$('cliente-nombre').value,telefono:$('cliente-telefono').value,productos:cesta.map(x=>({marca:x.marca,producto:x.producto,cantidad:x.cantidad}))})});
    const j=await r.json(); if(!r.ok)throw new Error(j.mensaje||'No se pudo registrar');
    const total=cesta.reduce((a,x)=>a+x.precio*x.cantidad,0);
    const lineas=[`Hola, deseo confirmar el pedido ${j.codigo}.`,`Cliente: ${$('cliente-nombre').value}`,`Celular: ${$('cliente-telefono').value}`,''];
    cesta.forEach((x,i)=>{lineas.push(`${i+1}. ${x.producto}`,`Marca: ${x.marca}`,`Cantidad: ${x.cantidad}`,`Subtotal: ${dinero(x.precio*x.cantidad)}`,'');});
    lineas.push(`Total: ${dinero(total)}`,'El pedido está pendiente de confirmación.');
    const url=['https://','wa.me/','51950298908','?text=',encodeURIComponent(lineas.join('\n'))].join('');
    cesta=[]; guardarCesta(); renderCesta(); $('modal-cliente').classList.add('hidden'); cerrarCesta();
    window.open(url,'_blank') || (window.location.href=url);
  } catch(error){ mensaje('mensaje-cliente',error.message,'error'); }
  finally{boton.disabled=false;boton.textContent='Registrar y abrir WhatsApp';}
};

fetch('/api/productos').then(r=>r.json()).then(j=>{catalogo=j.productos||[];$('nota').textContent=`Inventario del ${j.fecha_stock||'día'} · ${catalogo.length} productos`;}).catch(()=>$('nota').textContent='No se pudo cargar el inventario');
renderCesta();
