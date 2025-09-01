const API = `${window.location.protocol}//${window.location.hostname}:5000`;

const els = {
  graf: null,
  tbody: null,
  mediaT: null,
  mediaU: null,
  chatInput: null,
  chatBox: null,
  btnChat: null,
  btnSeed: null
};

document.addEventListener("DOMContentLoaded", () => {
  els.tbody = document.getElementById("tbody");
  els.mediaT = document.getElementById("mediaT");
  els.mediaU = document.getElementById("mediaU");
  els.chatInput = document.getElementById("chatInput");
  els.chatBox = document.getElementById("chatBox");
  els.btnChat = document.getElementById("btnChat");
  els.btnSeed = document.getElementById("btnSeed");

  els.btnChat.addEventListener("click", enviarChat);
  els.btnSeed.addEventListener("click", seedar);

  setupChart();
  tick();
  setInterval(tick, 5000);
});

async function seedar(){
  try {
    await fetch(`${API}/seed?n=40&interval_ms=120`, { method: "POST" });
  } catch {}
}

function setupChart(){
  const ctx = document.getElementById("grafico").getContext("2d");
  els.graf = new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [
      { label: "Temperatura (°C)", data: [], borderWidth: 2, fill: false },
      { label: "Umidade (%)", data: [], borderWidth: 2, fill: false }
    ]},
    options: {
      animation: false,
      responsive: true,
      scales: { x: { display: false } }
    }
  });
}

async function tick(){
  try {
    const [s, a] = await Promise.all([
      fetch(`${API}/series?limit=200`).then(r=>r.json()),
      fetch(`${API}/analise?limit=200`).then(r=>r.json())
    ]);

    // Update chart
    els.graf.data.labels = s.time;
    els.graf.data.datasets[0].data = s.temperatura;
    els.graf.data.datasets[1].data = s.umidade;
    els.graf.update();

    // Update table (últimos 30, mais recentes em cima)
    const dados = (await fetch(`${API}/dados?limit=30`).then(r=>r.json())).reverse();
    els.tbody.innerHTML = dados.map(p => `
      <tr>
        <td>${p.time}</td>
        <td>${p.temperatura.toFixed(2)}</td>
        <td>${p.umidade.toFixed(2)}</td>
      </tr>
    `).join("");

    // Stats
    els.mediaT.textContent = a.temperatura?.media ? a.temperatura.media.toFixed(2) : "—";
    els.mediaU.textContent = a.umidade?.media ? a.umidade.media.toFixed(2) : "—";

  } catch (e) {
    // Silencia para demo
  }
}

async function enviarChat(){
  const m = els.chatInput.value.trim();
  if(!m) return;
  els.chatBox.innerHTML += `<div><b>Você:</b> ${m}</div>`;
  try {
    const r = await fetch(`${API}/chat/${encodeURIComponent(m)}`).then(r=>r.json());
    els.chatBox.innerHTML += `<div><b>Bot:</b> ${r.resposta}</div>`;
  } catch {
    els.chatBox.innerHTML += `<div><b>Bot:</b> erro ao responder</div>`;
  }
  els.chatInput.value = "";
  els.chatBox.scrollTop = els.chatBox.scrollHeight;
}
