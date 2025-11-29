const API = `http://192.168.68.111:5000`;

const els = {
  loginModal: document.getElementById('loginModal'),
  mainContent: document.getElementById('mainContent'),
  loginForm: document.getElementById('loginForm'),
  loginError: document.getElementById('loginError'),
  logoutBtn: document.getElementById('logoutBtn'),
  
  currentTemp: document.getElementById('currentTemp'),
  currentHumidity: document.getElementById('currentHumidity'),
  currentLight: document.getElementById('currentLight'),
  currentWaterLevel: document.getElementById('currentWaterLevel'),
  tempTrend: document.getElementById('tempTrend'),
  humidityTrend: document.getElementById('humidityTrend'),
  lightTrend: document.getElementById('lightTrend'),
  waterTrend: document.getElementById('waterTrend'),
  
  connectionStatus: document.getElementById('connectionStatus'),
  dataCount: document.getElementById('dataCount'),
  
  graf: null,
  tbody: document.getElementById("tbody"),
  
  mediaT: document.getElementById("mediaT"),
  mediaU: document.getElementById("mediaU"),
  mediaLight: document.getElementById("mediaLight"),
  mediaWater: document.getElementById("mediaWater"),
  tempMediaTrend: document.getElementById("tempMediaTrend"),
  humidityMediaTrend: document.getElementById("humidityMediaTrend"),
  lightMediaTrend: document.getElementById("lightMediaTrend"),
  waterMediaTrend: document.getElementById("waterMediaTrend"),
  
  chatInput: document.getElementById("chatInput"),
  chatBox: document.getElementById("chatBox"),
  btnChat: document.getElementById("btnChat")
};

const state = {
  systemReady: false,
  connectionStatus: 'checking',
  currentSessionId: null,
  isAuthenticated: false,
  previousData: null,
  chartData: {
    labels: [],
    temperatura: [],
    umidade: [],
    luminosidade: [],
    nivel_agua: []
  },
  estufaData: {
    mediaTemperatura: 0,
    mediaUmidade: 0,
    mediaLuminosidade: 0,
    mediaNivelAgua: 0,
    lastUpdate: null,
    totalRegistros: 0
  }
};

document.addEventListener("DOMContentLoaded", () => {
  initializeApp();
});

function initializeApp() {
  setupEventListeners();
  setupChart();
  checkAuthentication();
  initializeLiquidBackground();
}

function setupEventListeners() {
  els.loginForm.addEventListener('submit', handleLogin);
  els.logoutBtn.addEventListener('click', handleLogout);
  
  els.btnChat.addEventListener('click', enviarChat);
  els.chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      enviarChat();
    }
  });
}

function setupChart() {
  const ctx = document.getElementById("grafico").getContext("2d");
  
  if (window.existingChart) {
    window.existingChart.destroy();
  }
  
  els.graf = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { 
          label: "Temperatura (°C)", 
          data: [], 
          borderWidth: 3,
          borderColor: '#00ff88',
          backgroundColor: 'rgba(0, 255, 136, 0.1)',
          fill: false,
          tension: 0.4,
          pointBackgroundColor: '#00ff88',
          pointBorderColor: '#000',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          yAxisID: 'y'
        },
        { 
          label: "Umidade (%)", 
          data: [], 
          borderWidth: 3,
          borderColor: '#00d4ff',
          backgroundColor: 'rgba(0, 212, 255, 0.1)',
          fill: false,
          tension: 0.4,
          pointBackgroundColor: '#00d4ff',
          pointBorderColor: '#000',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          yAxisID: 'y1'
        },
        { 
          label: "Luminosidade (lux)", 
          data: [], 
          borderWidth: 2,
          borderColor: '#fdcb6e',
          backgroundColor: 'rgba(253, 203, 110, 0.1)',
          fill: false,
          tension: 0.4,
          pointBackgroundColor: '#fdcb6e',
          pointBorderColor: '#000',
          pointBorderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          yAxisID: 'y2'
        }
      ]
    },
    options: {
      animation: {
        duration: 1000,
        easing: 'easeOutQuart'
      },
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index'
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(26, 26, 26, 0.95)',
          titleColor: '#fff',
          bodyColor: '#fff',
          borderColor: '#00ff88',
          borderWidth: 1,
          cornerRadius: 8,
          mode: 'index',
          intersect: false,
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (label) label += ': ';
              if (context.parsed.y !== null) {
                if (label.includes('Temperatura') || label.includes('Umidade')) {
                  label += context.parsed.y.toFixed(1);
                } else if (label.includes('Luminosidade')) {
                  label += Math.round(context.parsed.y);
                } else {
                  label += context.parsed.y;
                }
              }
              return label;
            }
          }
        }
      },
      scales: { 
        x: {
          display: true,
          grid: {
            color: 'rgba(255, 255, 255, 0.1)',
            drawBorder: false
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.7)',
            maxRotation: 45
          },
          title: {
            display: true,
            text: 'Tempo',
            color: 'rgba(255, 255, 255, 0.7)'
          }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          grid: {
            color: 'rgba(255, 255, 255, 0.1)',
            drawBorder: false
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.7)'
          },
          title: {
            display: true,
            text: 'Temperatura (°C)',
            color: '#00ff88'
          }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          grid: {
            drawOnChartArea: false,
          },
          ticks: {
            color: 'rgba(255, 255, 255, 0.7)'
          },
          title: {
            display: true,
            text: 'Umidade (%)',
            color: '#00d4ff'
          }
        },
        y2: {
          type: 'linear',
          display: false,
          position: 'right',
          grid: {
            drawOnChartArea: false,
          }
        }
      }
    }
  });
  
  window.existingChart = els.graf;
}

function initializeLiquidBackground() {
  const canvas = document.getElementById('liquidCanvas');
  const ctx = canvas.getContext('2d');
  
  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  
  const particles = [];
  const particleCount = 50;
  
  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      size: Math.random() * 3 + 1,
      speedX: (Math.random() - 0.5) * 0.5,
      speedY: (Math.random() - 0.5) * 0.5,
      color: `rgba(0, 255, 136, ${Math.random() * 0.1 + 0.05})`
    });
  }
  
  function animate() {
    ctx.fillStyle = 'rgba(10, 10, 10, 0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    particles.forEach(particle => {
      particle.x += particle.speedX;
      particle.y += particle.speedY;
      
      if (particle.x < 0 || particle.x > canvas.width) particle.speedX *= -1;
      if (particle.y < 0 || particle.y > canvas.height) particle.speedY *= -1;
      
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
      ctx.fillStyle = particle.color;
      ctx.fill();
    });
    
    requestAnimationFrame(animate);
  }
  
  animate();
}

function checkAuthentication() {
  const isAuthenticated = localStorage.getItem('isAuthenticated') === 'true';
  if (isAuthenticated) {
    showMainContent();
  } else {
    showLoginModal();
  }
}

async function handleLogin(e) {
  e.preventDefault();
  
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const loginBtn = e.target.querySelector('.login-btn');
  
  loginBtn.classList.add('loading');
  els.loginError.textContent = '';
  
  try {
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    if (username === 'admin' && password === '12345') {
      localStorage.setItem('isAuthenticated', 'true');
      showMainContent();
    } else {
      throw new Error('Credenciais inválidas. Use admin/12345');
    }
  } catch (error) {
    els.loginError.textContent = error.message;
  } finally {
    loginBtn.classList.remove('loading');
  }
}

function handleLogout() {
  localStorage.removeItem('isAuthenticated');
  showLoginModal();
  state.currentSessionId = null;
  const welcomeMessage = els.chatBox.querySelector('.welcome-message');
  els.chatBox.innerHTML = '';
  if (welcomeMessage) {
    els.chatBox.appendChild(welcomeMessage);
  }
}

function showLoginModal() {
  els.loginModal.classList.add('active');
  els.mainContent.classList.add('hidden');
  els.loginForm.reset();
  els.loginError.textContent = '';
}

function showMainContent() {
  els.loginModal.classList.remove('active');
  els.mainContent.classList.remove('hidden');
  checkSystemReady();
}

function updateConnectionStatus() {
  if (!els.connectionStatus) return;

  switch(state.connectionStatus) {
    case 'checking':
      els.connectionStatus.innerHTML = 'Conectando ao servidor e coletando dados...';
      els.connectionStatus.className = 'connection-status status-checking';
      break;
    case 'connected':
      els.connectionStatus.innerHTML = 'Conectado ao servidor - Dados em tempo real';
      els.connectionStatus.className = 'connection-status status-connected';
      break;
    case 'error':
      els.connectionStatus.innerHTML = 'Erro de conexão com o servidor';
      els.connectionStatus.className = 'connection-status status-error';
      break;
  }
}

async function checkSystemReady() {
  try {
    const response = await fetch(`${API}/dados?limit=1`);
    if (response.ok) {
      state.systemReady = true;
      state.connectionStatus = 'connected';
      updateConnectionStatus();
      
      console.log("✅ Sistema pronto com dados reais");
      tick();
      setInterval(tick, 5000);
    } else {
      throw new Error('Servidor não respondeu corretamente');
    }
  } catch (e) {
    console.log("Erro ao verificar sistema:", e);
    state.connectionStatus = 'error';
    updateConnectionStatus();
    setTimeout(checkSystemReady, 5000);
  }
}

function processDataForChart(dados) {
  if (!dados || !Array.isArray(dados) || dados.length === 0) {
    console.warn('Dados inválidos ou vazios:', dados);
    return;
  }

  try {
    const dadosOrdenados = [...dados].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const dadosLimitados = dadosOrdenados.slice(-20);
    
    const labels = dadosLimitados.map(item => {
      const date = new Date(item.timestamp);
      return date.toLocaleTimeString('pt-BR', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
      });
    });
    
    const temperaturas = dadosLimitados.map(item => parseFloat(item.temperatura));
    const umidades = dadosLimitados.map(item => parseFloat(item.umidade));
    const luminosidades = dadosLimitados.map(item => parseFloat(item.luminosidade || 0));
    const niveisAgua = dadosLimitados.map(item => parseFloat(item.nivel_reservatorio || 0));

    els.graf.data.labels = labels;
    els.graf.data.datasets[0].data = temperaturas;
    els.graf.data.datasets[1].data = umidades;
    els.graf.data.datasets[2].data = luminosidades;
    
    els.graf.update('none');
    
    state.chartData = {
      labels,
      temperatura: temperaturas,
      umidade: umidades,
      luminosidade: luminosidades,
      nivel_agua: niveisAgua
    };

    document.querySelector('.chart-container').classList.remove('chart-error', 'chart-loading');
    
    console.log('📊 Gráfico atualizado com', dadosLimitados.length, 'pontos de dados');
    
  } catch (error) {
    console.error('Erro ao processar dados para gráfico:', error);
    document.querySelector('.chart-container').classList.add('chart-error');
  }
}

function updateGlobalData(dados) {
  if (!dados || !Array.isArray(dados) || dados.length === 0) return;

  try {
    const temps = dados.map(item => parseFloat(item.temperatura)).filter(val => !isNaN(val));
    const umids = dados.map(item => parseFloat(item.umidade)).filter(val => !isNaN(val));
    const lights = dados.map(item => parseFloat(item.luminosidade || 0)).filter(val => !isNaN(val));
    const waters = dados.map(item => parseFloat(item.nivel_reservatorio || 0)).filter(val => !isNaN(val));

    if (temps.length > 0 && umids.length > 0) {
      state.estufaData = {
        mediaTemperatura: temps.reduce((a, b) => a + b, 0) / temps.length,
        mediaUmidade: umids.reduce((a, b) => a + b, 0) / umids.length,
        mediaLuminosidade: lights.length ? lights.reduce((a, b) => a + b, 0) / lights.length : 0,
        mediaNivelAgua: waters.length ? waters.reduce((a, b) => a + b, 0) / waters.length : 0,
        lastUpdate: new Date().toISOString(),
        totalRegistros: dados.length
      };
    }
  } catch (error) {
    console.error('Erro ao atualizar dados globais:', error);
  }
}

function updateTable(dados) {
  if (!dados || !Array.isArray(dados)) return;

  try {
    const dadosOrdenados = [...dados].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    els.tbody.innerHTML = dadosOrdenados.map(item => `
      <tr>
        <td>${new Date(item.timestamp).toLocaleTimeString('pt-BR', { 
          hour: '2-digit', 
          minute: '2-digit',
          second: '2-digit'
        })}</td>
        <td>sim_01</td>
        <td>${parseFloat(item.temperatura).toFixed(1)}</td>
        <td>${parseFloat(item.umidade).toFixed(1)}</td>
        <td>${Math.round(parseFloat(item.luminosidade || 0))}</td>
        <td>${parseFloat(item.nivel_reservatorio || 0).toFixed(2)}</td>
      </tr>
    `).join("");
    
    els.dataCount.textContent = `${dados.length} registros`;
    
  } catch (error) {
    console.error('Erro ao atualizar tabela:', error);
  }
}

function updateTrendIndicators(currentData, previousData) {
  if (!previousData) return;

  const tempChange = currentData.mediaTemperatura - previousData.mediaTemperatura;
  updateTrendElement(els.tempTrend, tempChange);
  
  const humidityChange = currentData.mediaUmidade - previousData.mediaUmidade;
  updateTrendElement(els.humidityTrend, humidityChange);
  
  const lightChange = currentData.mediaLuminosidade - previousData.mediaLuminosidade;
  updateTrendElement(els.lightTrend, lightChange);
  
  const waterChange = currentData.mediaNivelAgua - previousData.mediaNivelAgua;
  updateTrendElement(els.waterTrend, waterChange);
}

function updateTrendElement(element, change) {
  const absChange = Math.abs(change);
  if (absChange < 0.1) {
    element.textContent = 'Estável';
  } else if (change > 0) {
    element.textContent = `Subindo`;
  } else {
    element.textContent = `Descendo`;
  }
}

function updateCurrentValues() {
  const data = state.estufaData;
  
  els.currentTemp.textContent = data.mediaTemperatura ? data.mediaTemperatura.toFixed(1) : '--';
  els.currentHumidity.textContent = data.mediaUmidade ? data.mediaUmidade.toFixed(1) : '--';
  els.currentLight.textContent = data.mediaLuminosidade ? Math.round(data.mediaLuminosidade) : '--';
  els.currentWaterLevel.textContent = data.mediaNivelAgua ? data.mediaNivelAgua.toFixed(2) : '--';
  
  els.mediaT.textContent = data.mediaTemperatura ? data.mediaTemperatura.toFixed(1) : '—';
  els.mediaU.textContent = data.mediaUmidade ? data.mediaUmidade.toFixed(1) : '—';
  els.mediaLight.textContent = data.mediaLuminosidade ? Math.round(data.mediaLuminosidade) : '—';
  els.mediaWater.textContent = data.mediaNivelAgua ? data.mediaNivelAgua.toFixed(2) : '—';
  
  els.tempMediaTrend.textContent = 'Estável';
  els.humidityMediaTrend.textContent = 'Estável';
  els.lightMediaTrend.textContent = 'Estável';
  els.waterMediaTrend.textContent = 'Estável';
}

async function tick() {
  if (!state.systemReady) return;

  try {
    console.log('🔄 Buscando dados do servidor...');
    
    const response = await fetch(`${API}/dados?limit=20`);
    
    if (!response.ok) {
      throw new Error(`Erro HTTP: ${response.status}`);
    }
    
    const dados = await response.json();
    
    if (!Array.isArray(dados) || dados.length === 0) {
      throw new Error('Dados recebidos não são um array válido');
    }

    console.log('✅ Dados recebidos:', dados.length, 'registros');
    
    const previousData = state.previousData;
    state.previousData = { ...state.estufaData };

    processDataForChart(dados);
    updateTable(dados);
    updateGlobalData(dados);
    updateCurrentValues();
    
    if (previousData) {
      updateTrendIndicators(state.estufaData, previousData);
    }

    state.connectionStatus = 'connected';
    updateConnectionStatus();

  } catch (error) {
    console.error("❌ Erro ao atualizar dados:", error);
    state.connectionStatus = 'error';
    updateConnectionStatus();
    document.querySelector('.chart-container').classList.add('chart-error');
  }
}

async function enviarChat() {
  const mensagem = els.chatInput.value.trim();
  if (!mensagem) return;

  addMessageToChat(mensagem, 'user');
  els.chatInput.value = "";
  
  const thinking = showTypingIndicator();
  
  els.chatInput.disabled = true;
  els.btnChat.disabled = true;

  try {
    const resposta = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ 
        mensagem: mensagem,
        session_id: state.currentSessionId 
      })
    });

    if (!resposta.ok) {
      throw new Error(`Erro HTTP: ${resposta.status}`);
    }

    const data = await resposta.json();
    
    if (data.session_id) {
      state.currentSessionId = data.session_id;
    }
    
    thinking.remove();
    
    // Verificar se tem relatório para download
    if (data.tem_relatorio && data.url_download) {
      addMessageToChat(data.resposta, 'bot');
      
      // Adicionar botão de download
      const downloadDiv = document.createElement('div');
      downloadDiv.className = 'download-section';
      downloadDiv.innerHTML = `
        <div class="download-card">
          <div class="download-info">
            <h4>📊 Relatório Gerado</h4>
            <p>Dados completos da estufa + análise inteligente</p>
            <a href="${API}${data.url_download}" class="download-btn" download>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" stroke-width="2"/>
                <polyline points="7,10 12,15 17,10" stroke="currentColor" stroke-width="2" fill="none"/>
                <line x1="12" y1="15" x2="12" y2="3" stroke="currentColor" stroke-width="2"/>
              </svg>
              Baixar CSV
            </a>
          </div>
        </div>
      `;
      
      els.chatBox.appendChild(downloadDiv);
    } else {
      addMessageToChat(data.resposta, 'bot');
    }

  } catch (err) {
    console.error('Erro no chat:', err);
    thinking.remove();
    addMessageToChat('❌ Erro ao processar sua mensagem. Tente novamente.', 'bot');
  } finally {
    els.chatInput.disabled = false;
    els.btnChat.disabled = false;
    els.chatInput.focus();
  }
}

function addMessageToChat(texto, tipo) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${tipo}-message`;
  
  const timestamp = new Date().toLocaleTimeString('pt-BR', { 
    hour: '2-digit', 
    minute: '2-digit' 
  });

  let conteudoHtml;

  if (tipo === 'bot') {
    // troca quebras de linha por <br> pra deixar o analítico bonitão
    const safeText = texto.replace(/\n/g, '<br>');
    conteudoHtml = `
      <div class="bot-avatar">🌱</div>
      <div class="message-content">
        <div class="message-text">${safeText}</div>
        <div class="message-time">${timestamp}</div>
      </div>
    `;
  } else {
    conteudoHtml = `
      <div class="message-content">
        <div class="message-text">${texto}</div>
        <div class="message-time">${timestamp}</div>
      </div>
    `;
  }
  
  messageDiv.innerHTML = conteudoHtml;
  
  els.chatBox.appendChild(messageDiv);
  els.chatBox.scrollTop = els.chatBox.scrollHeight;
}

function showTypingIndicator() {
  const thinking = document.createElement('div');
  thinking.className = 'message bot-message';
  thinking.innerHTML = `
    <div class="bot-avatar">🌱</div>
    <div class="message-content">
      <div class="typing-indicator">
        <div class="typing-text">Pensando</div>
        <div class="typing-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  `;
  
  els.chatBox.appendChild(thinking);
  els.chatBox.scrollTop = els.chatBox.scrollHeight;
  return thinking;
}

window.estufaData = state.estufaData;
window.state = state;
