import { API_BASE } from "./config.js";

async function ping() {
  try {
    const r = await fetch(`${API_BASE}/status`);
    const j = await r.json();
    document.querySelector("#status").textContent = j.ok ? `OK (${j.port})` : "Error";
  } catch {
    document.querySelector("#status").textContent = "Sin conexión";
  }
}

function crc(n){
  return Number(n||0).toLocaleString("es-CR",{style:"currency",currency:"CRC"});
}

async function cargarFacturas() {
  const res = await fetch(`${API_BASE}/facturas`);
  const data = await res.json();

  const tbody = document.querySelector("#tbl tbody");
  tbody.innerHTML = "";
  let pendientes = 0, total = 0;
  const hoy = new Date().toISOString().slice(0,10);
  let vencidas = 0, porVencer = 0;

  data.forEach(f => {
    total += Number(f.monto || 0);
    const esPend = (f.estado || "pendiente") === "pendiente";
    if (esPend) pendientes += 1;
    if (esPend && f.vence < hoy) vencidas += 1;
    if (esPend && f.vence >= hoy) porVencer += 1;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${f.id}</td>
      <td>${f.cliente}</td>
      <td>${crc(f.monto)}</td>
      <td>${f.vence}</td>
      <td>${f.estado}</td>
      <td>
        ${f.estado !== "pagada" ? `<button class="btn" data-pagar="${f.id}">Marcar pagada</button>` : `<span class="ok">Pagada</span>`}
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelector("#totales").innerText =
    `Total: ${crc(total)} · Pendientes: ${pendientes}`;

  // Tarjetas de resumen
  document.querySelector("#r-total").textContent = crc(total);
  document.querySelector("#r-pendientes").textContent = pendientes;
  document.querySelector("#r-vencidas").textContent = vencidas;
  document.querySelector("#r-porvencer").textContent = porVencer;

  // Delegación para botón "Marcar pagada"
  tbody.querySelectorAll("button[data-pagar]").forEach(btn=>{
    btn.addEventListener("click", async ()=>{
      const id = btn.getAttribute("data-pagar");
      await fetch(`${API_BASE}/facturas/${id}`, {
        method:"PUT",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({estado:"pagada"})
      });
      await cargarFacturas();
    });
  });
}

async function crearFactura(factura){
  await fetch(`${API_BASE}/facturas`, {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(factura)
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  await ping();
  await cargarFacturas();

  const form = document.querySelector("#form-factura");
  form.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const factura = {
      cliente: form.cliente.value,
      monto: form.monto.value,
      vence: form.vence.value
    };
    await crearFactura(factura);
    form.reset();
    await cargarFacturas();
  });
});
