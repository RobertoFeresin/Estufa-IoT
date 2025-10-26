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

async function seedar() {
  try {
    await fetch(`${API}/seed?n=40&interval_ms=120`, { method: "POST" });
  } catch {}
}

function setupChart() {
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

async function tick() {
  try {
    const [s, a] = await Promise.all([
      fetch(`${API}/series?limit=200`).then(r=>r.json()),
      fetch(`${API}/analise?limit=200`).then(r=>r.json())
    ]);

    els.graf.data.labels = s.time;
    els.graf.data.datasets[0].data = s.temperatura;
    els.graf.data.datasets[1].data = s.umidade;
    els.graf.update();

    const dados = (await fetch(`${API}/dados?limit=30`).then(r=>r.json())).reverse();
    els.tbody.innerHTML = dados.map(p => `
      <tr>
        <td>${p.time}</td>
        <td>${p.temperatura.toFixed(2)}</td>
        <td>${p.umidade.toFixed(2)}</td>
      </tr>
    `).join("");

    els.mediaT.textContent = a.temperatura?.media ? a.temperatura.media.toFixed(2) : "—";
    els.mediaU.textContent = a.umidade?.media ? a.umidade.media.toFixed(2) : "—";

  } catch (e) {
    // ignora erros para demo
  }
}

// =========================
// 🔥 Chat IA Local (Ollama) + CSV Inteligente
// =========================
// Atualize a função enviarChat() para usar as novas classes:

async function enviarChat() {
  const m = els.chatInput.value.trim();
  if (!m) return;

  // Exibe mensagem do usuário (direita)
  const userMessage = document.createElement('div');
  userMessage.className = 'message user-message';
  userMessage.textContent = m;
  els.chatBox.appendChild(userMessage);
  
  els.chatInput.value = "";
  els.chatBox.scrollTop = els.chatBox.scrollHeight;

  // Indicador "digitando..." (esquerda)
  const thinking = document.createElement('div');
  thinking.className = 'typing-indicator';
  thinking.innerHTML = `
    <div class="typing-text">Digitando</div>
    <div class="typing-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  `;
  els.chatBox.appendChild(thinking);
  els.chatBox.scrollTop = els.chatBox.scrollHeight;

  els.chatInput.disabled = true;
  els.btnChat.disabled = true;

  try {
    // 🧠 Intercepta mensagens que pedem dados ou exportação
    if (/\b(csv|exportar|baixar|dados|arquivo|relatório)\b/i.test(m)) {
      thinking.remove();
      const botMessage = document.createElement('div');
      botMessage.className = 'message bot-message';
      botMessage.innerHTML = `
        📊 Tudo pronto! Você pode baixar os dados da estufa clicando no botão abaixo:<br><br>
        <a href="${API}/export.csv" class="btn-download" target="_blank" rel="noopener">⬇️ Baixar CSV</a>
      `;
      els.chatBox.appendChild(botMessage);
      els.chatBox.scrollTop = els.chatBox.scrollHeight;
      return;
    }

    // 🤖 Chamada para a IA local
    const res = await fetch("http://localhost:11434/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "qwen2:1.5b",
        stream: false,
        messages: [
          { 
            role: "system", 
            content: "Você é um assistente técnico da Estufa IoT. Responda de forma clara, concisa e sempre em português do Brasil." 
          },
          { role: "user", content: m }
        ]
      })
    });

    if (!res.ok) throw new Error("Erro na requisição");
    const data = await res.json();

    const resposta = (data.message?.content || data.response || "Sem resposta.")
      .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}]/gu, '')
      .trim();

    thinking.remove();
    const botMessage = document.createElement('div');
    botMessage.className = 'message bot-message';
    botMessage.textContent = resposta;
    els.chatBox.appendChild(botMessage);
    
  } catch (err) {
    console.error(err);
    thinking.remove();
    const errorMessage = document.createElement('div');
    errorMessage.className = 'message bot-message';
    errorMessage.textContent = '❌ Erro ao conectar com a IA local.';
    els.chatBox.appendChild(errorMessage);
  } finally {
    els.chatInput.disabled = false;
    els.btnChat.disabled = false;
    els.chatBox.scrollTop = els.chatBox.scrollHeight;
    els.chatInput.focus();
  }
}