document.querySelectorAll('.status-btn').forEach((button) => {
  button.addEventListener('click', async () => {
    const card = button.closest('.order-card');
    const estado = button.dataset.status;
    button.disabled = true;
    try {
      const response = await fetch(`/admin/pedidos/${card.dataset.orderId}/estado`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({estado})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.mensaje || 'No se pudo actualizar');
      const badge = card.querySelector('.badge');
      badge.textContent = result.estado;
      badge.className = `badge ${result.estado.toLowerCase()}`;
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
    }
  });
});
