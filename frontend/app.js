document.addEventListener('DOMContentLoaded', () => {
  const btn = document.querySelector('#btnCobrar');
  const out = document.querySelector('#salida');

  async function generarResumen(texto) {
  const r = await fetch('http://127.0.0.1:5055/ia/resumen-cobro', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({ texto })
});

});

    });
    const data = await r.json();
    if (!data.ok) throw new Error('IA falló');
    return data.respuesta;
  }

  btn.addEventListener('click', async () => {
    try {
      btn.disabled = true; btn.textContent = 'Procesando...';
      out.textContent = 'Consultando IA...';
      const respuesta = await generarResumen('Datos de cobro del cliente...');
      out.textContent = respuesta;
    } catch (e) {
      console.error(e);
      out.textContent = 'Error consultando IA';
    } finally {
      btn.disabled = false; btn.textContent = 'Cobrar';
    }
  });
});
