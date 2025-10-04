// ===== Config =====
const API_BASE = "/api";

// ===== Util =====
const $ = s => document.querySelector(s);
const fmt = n => new Intl.NumberFormat('es-CR', { maximumFractionDigits: 0 }).format(Number(n || 0));

function getToken(){ return localStorage.getItem('token') || ''; }
function setToken(t){ localStorage.setItem('token', t || ''); renderTokenState(); }
function clearToken(){ localStorage.removeItem('token'); renderTokenState(); }

function headersJSON(){
  const h = { 'Content-Type': 'application/json' };
  const t = getToken(); if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}
function headersAuth(){
  const h = {};
  const t = getToken(); if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

function renderTokenState(){
  const el = $('#tokenState');
  if (el) el.textContent = getToken() ? 'Token cargado' : 'Sin token';
}

// ===== Acceso =====
async function doLogin(){
  const email = $('#email')?.value.trim();
  const pass  = $('#pass')?.value;
  if(!email || !pass){ alert('Complete email y clave'); return; }
  try{
    await fetch(`${API_BASE}/auth/register`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password: pass})
    });

    const r = await fetch(`${API_BASE}/auth/login`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password: pass})
    });
    const j = await r.json();
    if(!r.ok){ throw new Error(j.error || 'login_fail'); }
    setToken(j.access_token);
    alert('Token guardado.');
  }catch(e){
    console.error(e);
    alert('Error de acceso');
  }
}

async function probarToken(){
  try{
    const r = await fetch(`${API_BASE}/users`, { headers: headersAuth() });
    if(!r.ok) throw new Error('token inválido');
    const j = await r.json();
    alert(`OK. Usuarios sample: ${j.length}`);
  }catch(e){
    alert('Token inválido o vencido');
  }
}

// ===== Listado =====
async function listar(){
  const qs = [];
  const d = $('#desde')?.value; if(d) qs.push(`desde=${encodeURIComponent(d)}`);
  const h = $('#hasta')?.value; if(h) qs.push(`hasta=${encodeURIComponent(h)}`);
  const url = `${API_BASE}/cobros${qs.length?`?${qs.join('&')}`:''}`;

  const info = $('#listInfo'); if(info) info.textContent = 'Cargando...';
  try{
    const r = await fetch(url, { headers: headersAuth() });
    const j = await r.json();
    if(!r.ok) throw new Error(j.error||'list_fail');

    const tb = $('#tbl tbody'); if(!tb) return;
    tb.innerHTML = '';
    j.forEach(row=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.id}</td>
        <td>${row.cliente||row.descripcion||''}</td>
        <td>₡${fmt(row.monto)}</td>
        <td>${row.vence||''}</td>
        <td>${row.estado}</td>
        <td>${row.referencia||''}</td>
        <td>
          ${row.estado==='pendiente' ? `<button data-id="${row.id}" class="mini cobrar">Cobrar</button>` : '<span class="ok">Pagado</span>'}
        </td>
      `;
      tb.appendChild(tr);
    });
    if(info) info.textContent = `${j.length} registros`;
  }catch(e){
    console.error(e);
    if(info) info.textContent = 'Error';
    alert('Error al listar.');
  }
}

// ===== Cobrar =====
async function cobrar(id){
  if(!confirm(`Marcar como pagado el ID ${id}?`)) return;
  try{
    const r = await fetch(`${API_BASE}/cobros/${id}/cobrar`, { method:'POST', headers: headersAuth() });
    const j = await r.json();
    if(!r.ok) throw new Error(j.error||'cobrar_fail');
    await listar();
  }catch(e){
    console.error(e);
    alert('No se pudo cobrar.');
  }
}

// ===== Exportar CSV =====
function exportar(){
  const t = getToken();
  if(!t){ alert('Primero acceda y guarde token.'); return; }
  const url = `${API_BASE}/cobros/export`;
  fetch(url, { headers: headersAuth() })
    .then(r => { if(!r.ok) throw new Error('export_fail'); return r.blob(); })
    .then(b => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(b);
      a.download = 'cobros_export.csv';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
    })
    .catch(()=> alert('No se pudo exportar.'));
}

// ===== Importar CSV =====
async function importarCSV(){
  const f = $('#fileCSV')?.files?.[0];
  if(!f){ alert('Seleccione un CSV'); return; }
  const fd = new FormData(); fd.append('file', f);
  const info = $('#importInfo'); if(info) info.textContent = 'Subiendo...';
  try{
    const r = await fetch(`${API_BASE}/cobros/import_csv`, { method:'POST', headers: headersAuth(), body: fd });
    const j = await r.json();
    if(!r.ok) throw new Error(j.error||'import_fail');
    if(info) info.textContent = `Importados: ${j.creados}`;
    await listar();
  }catch(e){
    console.error(e);
    if(info) info.textContent = 'Error';
    alert('Error al importar CSV.');
  }
}

// ===== Init =====
function initUI(){
  // Estado inicial de token
  renderTokenState();

  // Delegación de clicks
  document.addEventListener('click', (ev)=>{
    const t = ev.target;
    if(!(t instanceof Element)) return;
    if(t.id==='btnLogin') return void doLogin();
    if(t.id==='btnProbarToken') return void probarToken();
    if(t.id==='btnBorrarToken') { clearToken(); alert('Token eliminado.'); return; }
    if(t.id==='btnListar') return void listar();
    if(t.id==='btnExportar') return void exportar();
    if(t.id==='btnImportar') return void importarCSV();
    if(t.classList.contains('cobrar')) return void cobrar(t.dataset.id);
  });
}

// Corre cuando el DOM ya está listo (por si falla el defer)
document.addEventListener('DOMContentLoaded', initUI);
