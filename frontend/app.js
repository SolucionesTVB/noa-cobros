import { API_BASE } from "./config.js";

const $ = (s)=>document.querySelector(s);
const tbody = $("#tbl tbody");

function crc(n){ return Number(n||0).toLocaleString("es-CR",{style:"currency",currency:"CRC"}); }

async function ping(){
  try{
    const r = await fetch(`${API_BASE}/status`);
    const j = await r.json();
    $("#status").textContent = j.ok ? `OK (${j.port})` : "Error";
  }catch{ $("#status").textContent = "Sin conexión"; }
}

async function cargar(){
  const r = await fetch(`${API_BASE}/facturas`);
  const data = await r.json();

  tbody.innerHTML = "";
  let total=0, pend=0, venc=0, porv=0;
  const hoy = new Date().toISOString().slice(0,10);

  data.forEach(f=>{
    total += Number(f.monto||0);
    if((f.estado||"pendiente")==="pendiente"){
      pend++;
      if(f.vence<hoy) venc++; else porv++;
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${f.id}</td>
      <td>${f.cliente}</td>
      <td>${crc(f.monto)}</td>
      <td>${f.vence}</td>
      <td>${f.estado}</td>
      <td>
        ${f.estado!=="pagada"
          ? `<button class="btn" data-pagar="${f.id}">Marcar pagada</button>`
          : `<span class="ok">Pagada</span>`}
      </td>`;
    tbody.appendChild(tr);
  });

  $("#r-total").textContent = crc(total);
  $("#r-pend").textContent = pend;
  $("#r-venc").textContent = venc;
  $("#r-porv").textContent = porv;

  tbody.querySelectorAll("[data-pagar]").forEach(btn=>{
    btn.addEventListener("click", async ()=>{
      const id = btn.getAttribute("data-pagar");
      await fetch(`${API_BASE}/facturas/${id}`, {
        method:"PUT",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({estado:"pagada"})
      });
      await cargar();
    });
  });
}

async function crear(e){
  e.preventDefault();
  const f = e.target;
  const payload = {
    cliente: f.cliente.value,
    monto: f.monto.value,
    vence: f.vence.value
  };
  await fetch(`${API_BASE}/facturas`, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  f.reset();
  await cargar();
}

window.addEventListener("DOMContentLoaded", async ()=>{
  await ping();
  await cargar();
  $("#form-factura").addEventListener("submit", crear);
});
