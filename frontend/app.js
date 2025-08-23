document.addEventListener('DOMContentLoaded', () => {
  const btn = document.querySelector('#btnCobrar');
  const out = document.querySelector('#salida');

  if (!btn || !out) {
    alert('Falta el botón o el <p id="salida"> en el HTML');
    return;
  }

  async function generarResumen(texto) {
    const r = await fetch(`${window.API_BASE}/ia/resumen-cobro`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ texto })
    });
    const data = await r.json();
    if (!data.ok) throw new Error('IA falló');
    return data.respuesta;
  }

  btn.addEventListener('click', async () => {
    try {
      btn.disabled = true;
      btn.textContent = 'Procesando...';
      out.textContent = 'Consultando IA...';
      const respuesta = await generarResumen('Datos de cobro del cliente...');
      out.textContent = respuesta;
    } catch (e) {
      console.error(e);
      out.textContent = 'Error consultando IA';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Cobrar';
    }
  });
});
