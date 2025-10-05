// frontend/app.js — NOA Cobros (modo abierto)
(function () {
  const d = document;
  const API = '/api';

  const $desde = d.querySelector('#desde');
  const $hasta = d.querySelector('#hasta');
  const $btnListar = d.querySelector('#btnListar');
  const $btnExport = d.querySelector('#btnExport');
  const $file = d.querySelector('#fileCsv');
  const $btnImport = d.querySelector('#btnImport');
  const $tbody = d.querySelector('#tbody');

  function alertx(m){ window.alert(m); }

  async function req(path, opts={}) {
    const headers = new Headers(opts.headers || {});
    if (!headers.has('Content-Type') && !(opts.body instanceof FormData)) {
      headers.set('Content-Type','application/json');
    }
    const res = await fetch(API + path, { ...opts, headers });
    return res;
  }

  $btnListar?.addEventListener('click', async ()=>{
    try {
      const q = new URLSearchParams();
      if ($desde.value) q.set('desde', toISO($desde.value));
      if ($hasta.value) q.set('hasta', toISO($hasta.value));
      const r = await req('/cobros' + (q.toString()?`?${q}`:''), { method:'GET' });
      if (!r.ok) return alertx('Error al listar');
      const data = await r.json();
      renderRows(data||[]);
    } catch(e){ alertx('Error al listar'); }
  });

  $btnExport?.addEventListener('click', async ()=>{
    try {
      const r = await req('/cobros/export', { method:'GET' });
      if (!r.ok) return alertx('No se pudo exportar.');
      const blob = await r.blob();
      const a = d.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'cobros_export.csv';
      a.click();
      URL.revokeObjectURL(a.href);
    } catch { alertx('No se pudo exportar.'); }
  });

  $btnImport?.addEventListener('click', async ()=>{
    try {
      const f = $file.files?.[0];
      if (!f) return alertx('Elija un archivo CSV/XLSX');
      const fd = new FormData();
      fd.append('file', f);
      const r = await req('/cobros/import_csv', { method:'POST', body: fd });
      const j = await r.json().catch(()=> ({}));
      if (!r.ok || !j.ok) return alertx('Error al importar CSV.');
      alertx(`Importados: ${j.creados||j.insertados||0}`);
      $btnListar.click();
    } catch { alertx('Error al importar CSV.'); }
  });

  $tbody?.addEventListener('click', async (ev)=>{
    const id = ev.target?.getAttribute?.('data-cobrar');
    if (!id) return;
    if (!confirm(`¿Cobrar ${id}?`)) return;
    const r = await req(`/cobros/${id}/cobrar`, { method:'POST' });
    const j = await r.json().catch(()=> ({}));
    if (!r.ok || j.ok === False) return alertx('No se pudo cobrar.');
    alertx('Cobrado.');
    $btnListar.click();
  });

  function renderRows(items){
    const fmtMon = n => '₡' + Number(n||0).toLocaleString('es-CR',{maximumFractionDigits:0});
    const esc = s => String(s||'').replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));
    $tbody.innerHTML = (items||[]).map(x => `
      <tr>
        <td>${x.id}</td>
        <td>${esc(x.cliente||'')}</td>
        <td>${fmtMon(x.monto)}</td>
        <td>${esc(x.vence||'')}</td>
        <td>${esc(x.estado)}</td>
        <td>${esc(x.referencia||'')}</td>
        <td>
          ${x.estado==='pendiente'
            ? `<button class="btn btn-sm" data-cobrar="${x.id}">Cobrar</button>`
            : '<span class="tag ok">Pagado</span>'}
        </td>
      </tr>
    `).join('');
  }

  function toISO(dmy){
    if (!dmy) return '';
    const [dd,mm,aa] = String(dmy).split(/[\/\-]/);
    if (aa && mm && dd) return `${aa.padStart(4,'0')}-${mm.padStart(2,'0')}-${dd.padStart(2,'0')}`;
    return dmy;
  }
})();
