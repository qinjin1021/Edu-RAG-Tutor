/* 思小诘 · 苏格拉底学习助手 —— 前端逻辑（原生 JS，无依赖） */
'use strict';

/* ---------- 常量 ---------- */
const EMOTIONS = ['idle', 'think', 'happy', 'encourage', 'surprise'];
const PHASE_TEXT = { planning: '📝 规划中', learning: '📖 学习中', review: '🔍 查漏补缺', done: '🎉 已完成' };
const STATUS_TEXT = { pending: '待学习', learning: '学习中', consolidating: '巩固中', mastered: '已掌握', weak: '待加强' };
const STATUS_CLS = { pending: 'pending', learning: 'learning', consolidating: 'consolidating', mastered: 'mastered', weak: 'weak' };

const $ = (id) => document.getElementById(id);

const els = {
  characterImg: $('character-img'),
  voiceBtn: $('voice-btn'),
  phaseLabel: $('phase-label'),
  topicText: $('topic-text'),
  messageList: $('message-list'),
  chatInput: $('chat-input'),
  sendBtn: $('send-btn'),
  uploadBtn: $('upload-btn'),
  materialInput: $('material-input'),
  materialList: $('material-list'),
  progressHint: $('progress-hint'),
  progressBody: $('progress-body'),
  totalFill: $('total-fill'),
  totalText: $('total-text'),
  pointList: $('point-list'),
  sessionList: $('session-list'),
  newSessionBtn: $('new-session-btn'),
  toastContainer: $('toast-container'),
  settingsBtn: $('settings-btn'),
  settingsModal: $('settings-modal'),
  settingsTitle: $('settings-title'),
  wizardIntro: $('wizard-intro'),
  setApiKey: $('set-api-key'),
  setBaseUrl: $('set-base-url'),
  setModel: $('set-model'),
  keyStatus: $('key-status'),
  toggleKeyBtn: $('toggle-key-btn'),
  testConnBtn: $('test-conn-btn'),
  testResult: $('test-result'),
  settingsCancel: $('settings-cancel'),
  settingsSave: $('settings-save'),
  clearKeyBtn: $('clear-key-btn'),
  setSkin: $('set-skin'),
  setVoice: $('set-voice'),
  previewVoiceBtn: $('preview-voice-btn'),
  charBubble: $('char-bubble'),
  focusBtn: $('focus-btn'),
  historyBtn: $('history-btn'),
  historyModal: $('history-modal'),
  historyClose: $('history-close'),
};

/* ---------- 全局状态 ---------- */
const state = {
  session: null,       // 当前会话 {id, topic, status, progress...}
  phase: 'planning',   // 当前阶段
  emotion: 'idle',     // 当前立绘表情
  points: [],          // 知识点
  materials: [],       // 学习资料
  messages: [],        // 当前会话消息
  currentPointId: null,
  progress: 0,
  streaming: false,  // 是否正在接收 SSE 流
  voiceOn: localStorage.getItem('sixiaojie_voice') !== '0', // 语音默认开
  llmReady: false,   // 大模型 API 是否已配置（有 Key）
  // 皮肤系统：skin=当前皮肤ID，skinFiles=表情→文件名映射，skins=后端扫描的皮肤清单
  skin: 'default',
  skinFiles: { idle: 'idle.png', think: 'think.png', happy: 'happy.png', encourage: 'encourage.png', surprise: 'surprise.png' },
  skins: [],
  // 专注模式：开启后隐藏左侧形象面板（本地持久化）
  focusOn: localStorage.getItem('sixiaojie_focus') === '1',
};

/* ---------- 初始化 ---------- */
function init() {
  bindEvents();
  applyVoiceUI();
  applyFocusUI(); // 专注模式（本地持久化，启动即恢复）
  showWelcome();
  renderMaterials();
  loadSessions();
  loadSettings(); // 读取配置+皮肤音色；未配置 API Key 时弹出首启向导
  scheduleIdleAction(); // 待机随机小动作，让角色"活"起来

  // 健康检查，失败仅提示一次
  fetch('/api/health').catch(() => toast('无法连接后端服务，请确认服务已启动', 'error'));
}

function bindEvents() {
  els.sendBtn.addEventListener('click', onSend);
  els.chatInput.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); onSend(); }
  });
  els.chatInput.addEventListener('input', autoResizeInput);

  els.voiceBtn.addEventListener('click', toggleVoice);
  els.newSessionBtn.addEventListener('click', () => { closeHistory(); createSession(); });
  els.settingsBtn.addEventListener('click', () => openSettings(false));
  els.characterImg.addEventListener('click', pokeCharacter); // 点击立绘互动
  els.previewVoiceBtn.addEventListener('click', previewVoice); // 音色试听

  // 专注模式：隐藏左侧形象面板
  els.focusBtn.addEventListener('click', toggleFocus);
  // 历史学习弹窗
  els.historyBtn.addEventListener('click', openHistory);
  els.historyClose.addEventListener('click', closeHistory);
  els.historyModal.addEventListener('click', (ev) => {
    if (ev.target === els.historyModal) closeHistory();
  });

  // 设置弹窗
  els.settingsSave.addEventListener('click', saveSettings);
  els.settingsCancel.addEventListener('click', () => closeSettings());
  els.testConnBtn.addEventListener('click', testConnection);
  els.toggleKeyBtn.addEventListener('click', toggleKeyVisibility);
  els.clearKeyBtn.addEventListener('click', clearSavedKey);
  // 普通模式点遮罩关闭；向导模式强制完成配置，不给关闭入口
  els.settingsModal.addEventListener('click', (ev) => {
    if (ev.target === els.settingsModal && !settingsWizard) closeSettings();
  });

  // 输入栏 📎 与资料面板共用同一个文件选择器
  els.uploadBtn.addEventListener('click', () => els.materialInput.click());
  els.materialInput.addEventListener('change', () => {
    const file = els.materialInput.files[0];
    els.materialInput.value = ''; // 清空以便重复选择同一文件
    if (file) uploadMaterial(file);
  });
}

/* 输入框自适应高度 */
function autoResizeInput() {
  const t = els.chatInput;
  t.style.height = 'auto';
  t.style.height = Math.min(t.scrollHeight, 120) + 'px';
}

/* ---------- 语音开关 ---------- */
function toggleVoice() {
  state.voiceOn = !state.voiceOn;
  localStorage.setItem('sixiaojie_voice', state.voiceOn ? '1' : '0');
  applyVoiceUI();
  if (!state.voiceOn) stopTts();
}

function applyVoiceUI() {
  els.voiceBtn.textContent = state.voiceOn ? '🔊' : '🔇';
  els.voiceBtn.classList.toggle('off', !state.voiceOn);
  els.voiceBtn.title = state.voiceOn ? '点击关闭语音' : '点击开启语音';
}

/* ---------- 专注模式 ---------- */
function toggleFocus() {
  state.focusOn = !state.focusOn;
  localStorage.setItem('sixiaojie_focus', state.focusOn ? '1' : '0');
  applyFocusUI();
}

function applyFocusUI() {
  document.getElementById('app').classList.toggle('focus-mode', state.focusOn);
  els.focusBtn.classList.toggle('active', state.focusOn);
  els.focusBtn.title = state.focusOn ? '专注模式已开启：点击恢复形象展示' : '专注模式：隐藏左侧形象，专注学习';
}

/* ---------- 历史学习弹窗 ---------- */
function openHistory() {
  loadSessions(); // 打开时刷新列表（含进度）
  els.historyModal.classList.remove('hidden');
}

function closeHistory() {
  els.historyModal.classList.add('hidden');
}

/* ---------- 皮肤与立绘图源 ---------- */
/* 按当前皮肤取表情图路径：assets/character/<皮肤>/<表情文件>（支持 png/gif/webp 混用） */
function charAsset(emotion) {
  const f = state.skinFiles[emotion] || `${emotion}.png`;
  return `assets/character/${state.skin}/${f}`;
}

/* 预加载当前皮肤全部表情，切换时不闪烁 */
function preloadSkin() {
  EMOTIONS.forEach((e) => { const img = new Image(); img.src = charAsset(e); });
}

/* 应用皮肤：更新映射 → 刷新当前立绘 → 预加载（聊天头像/思考头像在渲染时实时取 charAsset） */
function applySkin(skinId) {
  const skin = state.skins.find((s) => s.id === skinId);
  if (!skin) return;
  state.skin = skin.id;
  state.skinFiles = skin.files || state.skinFiles;
  els.characterImg.src = charAsset(state.emotion);
  preloadSkin();
}

/* ---------- 立绘表情 ---------- */
function setEmotion(emotion) {
  if (!EMOTIONS.includes(emotion) || emotion === state.emotion) return;
  state.emotion = emotion;
  els.characterImg.src = charAsset(emotion);
  // 重新触发弹跳过渡动画
  els.characterImg.classList.remove('bounce');
  void els.characterImg.offsetWidth;
  els.characterImg.classList.add('bounce');
}

/* ---------- 立绘互动（生命力） ---------- */
const QUIPS = [
  '嘿嘿，小诘被你点到啦～',
  '学习累了？让眼睛休息一下吧！',
  '今天想学点什么呀？',
  '小提示：上传资料能让学习计划更贴合你哦！',
  '有疑问尽管说，不过我更想反问你，哈哈',
  '偷偷告诉你：每天学一点，坚持最可怕！',
];

/* 点击立绘：随机表情 + 弹跳 + 俏皮话气泡（+语音朗读） */
function pokeCharacter() {
  const pool = EMOTIONS.filter((e) => e !== state.emotion);
  setEmotion(pool[Math.floor(Math.random() * pool.length)]);
  const quip = QUIPS[Math.floor(Math.random() * QUIPS.length)];
  showCharBubble(quip);
  speak(quip);
}

let bubbleTimer = null;
function showCharBubble(text) {
  els.charBubble.textContent = text;
  els.charBubble.classList.add('show');
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => els.charBubble.classList.remove('show'), 2600);
}

/* 待机随机小动作：每 8~15 秒轻微摇摆一次 */
function scheduleIdleAction() {
  const delay = 8000 + Math.random() * 7000;
  setTimeout(() => {
    if (!state.streaming) {
      els.characterImg.classList.remove('wiggle');
      void els.characterImg.offsetWidth;
      els.characterImg.classList.add('wiggle');
    }
    scheduleIdleAction();
  }, delay);
}

function updatePhaseLabel() {
  els.phaseLabel.textContent = state.session ? (PHASE_TEXT[state.phase] || state.phase) : '💤 未开始';
}

function updateTopic() {
  els.topicText.textContent = (state.session && state.session.topic) ? state.session.topic : '开始你的学习吧';
}

/* ---------- Toast ---------- */
function toast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  els.toastContainer.appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 300); }, 3000);
}

/* ---------- 模型设置 / 首启向导 ---------- */
let settingsWizard = false; // true = 首启向导模式（不可取消，必须完成配置）

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.llmReady = !!data.configured;
    state.skins = data.skins || [];
    // 应用已保存的皮肤（三处形象统一在渲染时取 charAsset）
    if (data.skin) {
      state.skin = data.skin;
      state.skinFiles = data.skin_files || state.skinFiles;
      els.characterImg.src = charAsset(state.emotion);
      preloadSkin();
    }
    if (!data.configured) openSettings(true); // 首次使用 → 向导
  } catch (e) { /* 静默失败：聊天时还会兜底提示 */ }
}

/* 填充皮肤/音色下拉框（打开弹窗时刷新，便于热加皮肤后无需重启） */
function fillAppearanceControls(data) {
  els.setSkin.innerHTML = '';
  (data.skins || []).forEach((s) => {
    const opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.name;
    els.setSkin.appendChild(opt);
  });
  els.setSkin.value = data.skin || 'default';
  els.setVoice.innerHTML = '';
  (data.voices || []).forEach((v) => {
    const opt = document.createElement('option');
    opt.value = v.id;
    opt.textContent = v.name;
    els.setVoice.appendChild(opt);
  });
  els.setVoice.value = data.voice || 'zh-CN-xiaoyiNeural';
}

function openSettings(wizard) {
  settingsWizard = wizard;
  // 预填当前生效的 base_url / model / 皮肤 / 音色；Key 不回填，仅显示掩码状态
  fetch('/api/settings').then((r) => r.json()).then((data) => {
    els.setBaseUrl.value = data.base_url || '';
    els.setModel.value = data.model || '';
    els.keyStatus.textContent = data.configured ? `已配置 ${data.api_key_masked}` : '未配置';
    els.clearKeyBtn.classList.toggle('hidden', !data.configured);
    fillAppearanceControls(data);
  }).catch(() => {});
  els.settingsTitle.textContent = wizard ? '👋 欢迎使用思小诘' : '⚙️ 模型设置';
  els.wizardIntro.classList.toggle('hidden', !wizard);
  els.settingsCancel.classList.toggle('hidden', wizard);
  els.settingsSave.textContent = wizard ? '保存并开始学习' : '保存';
  els.setApiKey.value = '';
  els.setApiKey.type = 'password';
  els.toggleKeyBtn.textContent = '显示';
  hideTestResult();
  els.settingsModal.classList.remove('hidden');
  setTimeout(() => els.setApiKey.focus(), 50);
}

function closeSettings() {
  els.settingsModal.classList.add('hidden');
}

function toggleKeyVisibility() {
  const hidden = els.setApiKey.type === 'password';
  els.setApiKey.type = hidden ? 'text' : 'password';
  els.toggleKeyBtn.textContent = hidden ? '隐藏' : '显示';
}

/* 清除已保存的 Key（换账号/重新配置场景），URL 与模型保持当前值 */
async function clearSavedKey() {
  if (!confirm('确定清除已保存的 API Key 吗？清除后需要重新填写才能使用。')) return;
  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: '',
        base_url: els.setBaseUrl.value.trim(),
        model: els.setModel.value.trim(),
        clear_api_key: true,
      }),
    });
    const data = await res.json();
    state.llmReady = !!data.configured;
    els.keyStatus.textContent = data.configured ? `已配置 ${data.api_key_masked}` : '未配置';
    els.clearKeyBtn.classList.toggle('hidden', !data.configured);
    els.setApiKey.value = '';
    hideTestResult();
    toast('已清除保存的 Key', 'success');
  } catch (e) {
    toast('操作失败，请重试', 'error');
  }
}

function showTestResult(ok, message) {
  els.testResult.textContent = message;
  els.testResult.className = `test-result ${ok ? 'ok' : 'fail'}`;
}

function hideTestResult() {
  els.testResult.className = 'test-result hidden';
  els.testResult.textContent = '';
}

/* 测试连接：用弹窗当前填写的内容（Key 留空 = 沿用已保存的） */
async function testConnection() {
  const body = {
    api_key: els.setApiKey.value.trim(),
    base_url: els.setBaseUrl.value.trim(),
    model: els.setModel.value.trim(),
  };
  els.testConnBtn.disabled = true;
  els.testConnBtn.textContent = '测试中…';
  showTestResult(false, '正在连接，请稍候…');
  try {
    const res = await fetch('/api/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) showTestResult(true, `✅ 连接成功！模型回复：${data.reply}`);
    else showTestResult(false, `❌ 连接失败：${data.message || '请检查填写内容'}`);
  } catch (e) {
    showTestResult(false, '❌ 网络错误，请确认后端服务已启动');
  } finally {
    els.testConnBtn.disabled = false;
    els.testConnBtn.textContent = '🔌 测试连接';
  }
}

/* 保存设置：Key 留空 = 保持不变；URL/模型留空 = 恢复默认；皮肤/音色留空 = 保持不变 */
async function saveSettings() {
  const body = {
    api_key: els.setApiKey.value.trim(),
    base_url: els.setBaseUrl.value.trim(),
    model: els.setModel.value.trim(),
    skin: els.setSkin.value,
    voice: els.setVoice.value,
  };
  if (settingsWizard && !body.api_key && !state.llmReady) {
    showTestResult(false, '❌ 请先填写 API Key');
    els.setApiKey.focus();
    return;
  }
  els.settingsSave.disabled = true;
  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.llmReady = !!data.configured;
    if (settingsWizard && !data.configured) {
      showTestResult(false, '❌ 未检测到 API Key，请填写后再保存');
      els.setApiKey.focus();
      return;
    }
    applySkin(body.skin); // 皮肤即时生效（音色在后端即时生效）
    closeSettings();
    toast(settingsWizard ? '配置完成，开始学习吧！' : '设置已保存', 'success');
  } catch (e) {
    toast('保存失败，请重试', 'error');
  } finally {
    els.settingsSave.disabled = false;
  }
}

/* 试听所选音色：临时音色直接合成播放，无需保存 */
async function previewVoice() {
  const voice = els.setVoice.value;
  if (!voice) return;
  els.previewVoiceBtn.disabled = true;
  els.previewVoiceBtn.textContent = '试听中…';
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: '你好呀，我是思小诘，听听这个音色感觉怎么样？', voice }),
    });
    if (!res.ok) throw new Error(res.status);
    const blob = await res.blob();
    await playAudio(blob);
  } catch (e) {
    toast('试听失败：在线音色需要联网，请检查网络', 'error');
  } finally {
    els.previewVoiceBtn.disabled = false;
    els.previewVoiceBtn.textContent = '▶ 试听';
  }
}

/* ---------- 聊天渲染 ---------- */
function scrollToBottom() { els.messageList.scrollTop = els.messageList.scrollHeight; }

function showWelcome() {
  addSystemCard('👋 我是思小诘！点击右上角 🕘 的「新的学习」，或直接输入想学的主题开始吧～');
}

function addSystemCard(text) {
  const el = document.createElement('div');
  el.className = 'system-card';
  el.textContent = text;
  els.messageList.appendChild(el);
  scrollToBottom();
}

/* 渲染一条消息，返回 {bubble, txt} 便于流式追加 */
function renderMessage(role, content) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${role === 'user' ? 'user' : 'assistant'}`;
  if (role !== 'user') {
    const av = document.createElement('img');
    av.className = 'avatar';
    av.src = charAsset('idle');
    av.alt = '思小诘';
    wrap.appendChild(av);
  }
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  const icon = document.createElement('span');
  icon.className = 'b-icon';
  icon.textContent = '📋';
  const txt = document.createElement('span');
  txt.className = 'txt';
  txt.textContent = content || '';
  bubble.appendChild(icon);
  bubble.appendChild(txt);
  wrap.appendChild(bubble);
  els.messageList.appendChild(wrap);
  scrollToBottom();
  return { bubble, txt };
}

/* 含"学习总结"行（整条开头或另起一行）的消息 → 高亮总结卡片 */
function markSummaryIfNeed(bubble, text) {
  if (bubble && text && /(^|\n)\s*学习总结/.test(text)) bubble.classList.add('summary');
}

/* 含"🎉 阶段达成"的消息 → 高亮奖励卡片 */
function markRewardIfNeed(bubble, text) {
  if (bubble && text && /(^|\n)\s*🎉 阶段达成/.test(text)) bubble.classList.add('reward');
}

/* 阶段庆祝动画：emoji 飘落层（配合后端 reward 事件） */
function celebrate() {
  setEmotion('happy');
  const emojis = ['🎉', '✨', '⭐', '🎊', '💫', '🌟'];
  const layer = document.createElement('div');
  layer.className = 'celebration';
  for (let i = 0; i < 16; i++) {
    const s = document.createElement('span');
    s.textContent = emojis[Math.floor(Math.random() * emojis.length)];
    s.style.left = (3 + Math.random() * 94) + '%';
    s.style.animationDelay = (Math.random() * 0.7).toFixed(2) + 's';
    s.style.fontSize = (15 + Math.random() * 17).toFixed(0) + 'px';
    layer.appendChild(s);
  }
  document.body.appendChild(layer);
  setTimeout(() => layer.remove(), 3000);
}

/* 思考中指示 */
let thinkingEl = null;
function showThinking() {
  removeThinking();
  const wrap = document.createElement('div');
  wrap.className = 'msg assistant';
  wrap.innerHTML = `
    <img class="avatar" src="${charAsset('think')}" alt="思小诘">
    <div class="bubble thinking-bubble"><span class="dots"><i></i><i></i><i></i></span>思小诘思考中…</div>`;
  els.messageList.appendChild(wrap);
  thinkingEl = wrap;
  scrollToBottom();
}
function removeThinking() { if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; } }

/* 流式期间禁用输入 */
function setStreamingUI(on) {
  state.streaming = on;
  els.chatInput.disabled = on;
  els.sendBtn.disabled = on;
  els.uploadBtn.disabled = on;
  els.chatInput.placeholder = on ? '思小诘思考中…' : '和思小诘聊聊你想学什么…（Enter 发送，Shift+Enter 换行）';
}

/* ---------- 历史会话 ---------- */
async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    renderSessions(data.sessions || []);
  } catch (e) {
    toast('获取历史会话失败', 'error');
  }
}

function renderSessions(sessions) {
  els.sessionList.innerHTML = '';
  if (!sessions.length) {
    const hint = document.createElement('div');
    hint.className = 'panel-hint';
    hint.textContent = '暂无历史会话，点「新的学习」开始吧';
    els.sessionList.appendChild(hint);
    return;
  }
  sessions.forEach((s) => {
    const item = document.createElement('div');
    item.className = 'session-item' + (state.session && state.session.id === s.id ? ' active' : '');

    const main = document.createElement('div');
    main.className = 's-main';
    const topic = document.createElement('div');
    topic.className = 's-topic';
    topic.textContent = s.topic || '未命名主题';
    topic.title = s.topic || '';
    const row = document.createElement('div');
    row.className = 's-row';
    const bar = document.createElement('div');
    bar.className = 's-bar';
    const fill = document.createElement('i');
    fill.style.width = `${s.progress || 0}%`;
    bar.appendChild(fill);
    const pct = document.createElement('span');
    pct.className = 's-pct';
    pct.textContent = `${s.progress || 0}%`;
    row.appendChild(bar);
    row.appendChild(pct);
    main.appendChild(topic);
    main.appendChild(row);

    const del = document.createElement('button');
    del.className = 's-del';
    del.textContent = '✕';
    del.title = '删除会话';
    del.addEventListener('click', (ev) => { ev.stopPropagation(); deleteSession(s.id); });

    item.appendChild(main);
    item.appendChild(del);
    item.addEventListener('click', () => { closeHistory(); loadSession(s.id); });
    els.sessionList.appendChild(item);
  });
}

/* ---------- 会话生命周期 ---------- */
async function createSession() {
  if (state.streaming) { toast('请等待思小诘回复完成', 'error'); return null; }
  try {
    const res = await fetch('/api/sessions', { method: 'POST' });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    resetChat();
    state.session = data.session;
    state.phase = (data.session && data.session.status) || 'planning';
    state.points = [];
    state.materials = [];
    state.messages = [];
    state.currentPointId = null;
    state.progress = 0;
    applyPanels();
    updateTopic();
    updatePhaseLabel();
    setEmotion('happy');
    if (data.greeting) {
      renderMessage('assistant', data.greeting);
      speak(data.greeting); // 朗读问候语
    }
    loadSessions(); // 后台刷新列表
    return data.session;
  } catch (e) {
    toast('创建会话失败，请检查后端服务', 'error');
    return null;
  }
}

async function loadSession(id) {
  if (state.streaming) { toast('请等待思小诘回复完成', 'error'); return; }
  try {
    const res = await fetch(`/api/sessions/${id}`);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.session = data.session;
    state.phase = (data.session && data.session.status) || 'planning';
    state.points = data.points || [];
    state.materials = data.materials || [];
    state.messages = data.messages || [];
    state.currentPointId = null;
    state.progress = (data.session && data.session.progress) || 0;

    // 渲染全部历史消息
    removeThinking();
    els.messageList.innerHTML = '';
    if (!state.messages.length) showWelcome();
    state.messages.forEach((m) => {
      const { bubble } = renderMessage(m.role, m.content);
      markSummaryIfNeed(bubble, m.content);
      markRewardIfNeed(bubble, m.content);
    });

    updateTopic();
    updatePhaseLabel();
    applyPanels();
    setEmotion('idle');
    loadSessions(); // 刷新列表高亮
    scrollToBottom();
  } catch (e) {
    toast('加载会话失败', 'error');
  }
}

async function deleteSession(id) {
  if (!confirm('确定删除这个会话吗？')) return;
  try {
    const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(res.status);
    if (state.session && state.session.id === id) resetAll();
    loadSessions();
    toast('会话已删除', 'success');
  } catch (e) {
    toast('删除会话失败', 'error');
  }
}

/* 清空聊天区（保留面板由调用方刷新） */
function resetChat() {
  removeThinking();
  els.messageList.innerHTML = '';
}

/* 完全重置到无会话状态 */
function resetAll() {
  state.session = null;
  state.phase = 'planning';
  state.points = [];
  state.materials = [];
  state.messages = [];
  state.currentPointId = null;
  state.progress = 0;
  resetChat();
  showWelcome();
  updateTopic();
  updatePhaseLabel();
  applyPanels();
  setEmotion('idle');
}

/* ---------- 发送消息与 SSE 流解析 ---------- */
async function onSend() {
  const content = els.chatInput.value.trim();
  if (!content || state.streaming) return;
  // 未配置模型 API：引导用户先完成设置
  if (!state.llmReady) {
    toast('请先配置大模型 API（右上角 ⚙️），思小诘才能思考哦', 'error');
    openSettings(true);
    return;
  }
  // 无会话时先自动创建，第一条消息即学习主题
  if (!state.session) {
    const session = await createSession();
    if (!session) return;
  }
  els.chatInput.value = '';
  autoResizeInput();
  renderMessage('user', content);
  streamChat(content);
}

async function streamChat(content) {
  setStreamingUI(true);
  showThinking();
  setEmotion('think');

  let streamNode = null; // 当前流式助手气泡
  let fullText = '';     // 累积文本
  let doneReceived = false;

  const finish = (emotion) => {
    removeThinking();
    setStreamingUI(false);
    if (emotion) setEmotion(emotion);
  };

  /* 处理单条 SSE 事件 */
  const handleEvent = (obj) => {
    if (!obj || typeof obj !== 'object') return;
    switch (obj.type) {
      case 'delta':
        if (!streamNode) { removeThinking(); streamNode = renderMessage('assistant', ''); }
        fullText += obj.text || '';
        streamNode.txt.textContent = fullText; // pre-wrap 支持换行
        scrollToBottom();
        break;
      case 'emotion':
        setEmotion(obj.emotion); // 即时切换立绘
        break;
      case 'state':
        applyState(obj);
        if (obj.phase === 'done') markSummaryIfNeed(streamNode && streamNode.bubble, fullText);
        break;
      case 'reward':
        celebrate(); // 阶段达成：庆祝动画（气泡高亮在 done 时统一标记）
        break;
      case 'done':
        doneReceived = true;
        removeThinking();
        markSummaryIfNeed(streamNode && streamNode.bubble, fullText);
        markRewardIfNeed(streamNode && streamNode.bubble, fullText);
        finish(obj.emotion);
        speak(fullText); // 完成后朗读整段回复
        refreshSessionMeta();
        break;
      case 'error':
        toast(obj.message || '服务返回错误', 'error');
        break;
    }
  };

  /* 按 \n\n 分帧；final=true 时处理末尾无空行的残留帧 */
  const processBuffer = (final) => {
    const handleLine = (line) => {
      const t = line.trim();
      if (!t.startsWith('data:')) return;
      try { handleEvent(JSON.parse(t.slice(5).trim())); } catch (e) { /* 忽略坏帧 */ }
    };
    let idx;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      frame.split('\n').forEach(handleLine);
    }
    if (final && buffer.trim()) {
      buffer.split('\n').forEach(handleLine);
      buffer = '';
    }
  };

  let buffer = '';
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.session.id, content }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }); // chunk 跨帧拼接缓冲
      processBuffer(false);
    }
    buffer += decoder.decode();
    processBuffer(true);

    // 流结束但未收到 done 事件的兜底
    if (!doneReceived) {
      markSummaryIfNeed(streamNode && streamNode.bubble, fullText);
      markRewardIfNeed(streamNode && streamNode.bubble, fullText);
      finish('idle');
      if (fullText) speak(fullText);
      refreshSessionMeta();
    }
  } catch (e) {
    toast('消息发送失败，请检查网络或后端服务', 'error');
    finish('idle');
  }
}

/* state 事件：阶段 / 知识点 / 进度 */
function applyState(ev) {
  if (typeof ev.phase === 'string') {
    if (ev.phase !== state.phase) {
      const prev = state.phase;
      state.phase = ev.phase;
      updatePhaseLabel();
      // 进入查漏补缺阶段的系统提示卡
      if (ev.phase === 'review' && prev !== 'review') addSystemCard('🌸 进入查漏补缺阶段');
    }
    if (state.session) state.session.status = ev.phase;
  }
  if (Array.isArray(ev.points)) state.points = ev.points;
  if (typeof ev.progress === 'number') {
    state.progress = ev.progress;
    if (state.session) state.session.progress = ev.progress;
  }
  if (ev.current_point) state.currentPointId = ev.current_point.id;
  else if (ev.current_point === null) state.currentPointId = null;
  applyPanels(); // 即时刷新右栏
}

/* done 后轻量刷新会话元信息（主题/进度/列表），不重渲染聊天 */
async function refreshSessionMeta() {
  if (!state.session) return;
  try {
    const res = await fetch(`/api/sessions/${state.session.id}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.session) {
      state.session = data.session;
      state.progress = data.session.progress || state.progress;
      updateTopic();
      updatePhaseLabel();
      applyPanels();
    }
    loadSessions();
  } catch (e) { /* 静默失败 */ }
}

/* ---------- 右栏面板 ---------- */
/* status != planning 时进度区可见 */
function applyPanels() {
  const status = state.session ? state.session.status : null;
  const showProgress = !!(status && status !== 'planning');
  els.progressHint.classList.toggle('hidden', showProgress);
  els.progressBody.classList.toggle('hidden', !showProgress);
  if (showProgress) {
    renderProgress();
    renderPoints();
  }
  renderMaterials();
}

function renderProgress() {
  const p = Math.max(0, Math.min(100, state.progress || 0));
  els.totalFill.style.width = `${p}%`;
  els.totalText.textContent = `${p}%`;
}

function renderPoints() {
  els.pointList.innerHTML = '';
  if (!state.points.length) {
    const hint = document.createElement('div');
    hint.className = 'panel-hint';
    hint.textContent = '暂无知识点';
    els.pointList.appendChild(hint);
    return;
  }
  state.points.forEach((pt) => {
    const card = document.createElement('div');
    card.className = 'point-card' + (pt.id === state.currentPointId ? ' current' : '');

    const head = document.createElement('div');
    head.className = 'point-head';
    const name = document.createElement('span');
    name.className = 'point-name';
    name.textContent = pt.name || `知识点 ${pt.idx}`;
    name.title = pt.description || '';
    const badge = document.createElement('span');
    badge.className = 'badge ' + (STATUS_CLS[pt.status] || 'pending');
    badge.textContent = STATUS_TEXT[pt.status] || pt.status || '待学习';
    head.appendChild(name);
    head.appendChild(badge);

    const row = document.createElement('div');
    row.className = 'point-row';
    const bar = document.createElement('div');
    bar.className = 'point-bar';
    const fill = document.createElement('i');
    fill.style.width = `${pt.mastery || 0}%`;
    bar.appendChild(fill);
    const pct = document.createElement('span');
    pct.className = 'point-pct';
    pct.textContent = `${pt.mastery || 0}%`;
    row.appendChild(bar);
    row.appendChild(pct);

    card.appendChild(head);
    card.appendChild(row);
    els.pointList.appendChild(card);
  });
}

function renderMaterials() {
  els.materialList.innerHTML = '';
  if (!state.materials.length) {
    const hint = document.createElement('div');
    hint.className = 'panel-hint';
    hint.textContent = '上传资料可让学习计划更贴合你';
    els.materialList.appendChild(hint);
    return;
  }
  state.materials.forEach((m) => {
    const item = document.createElement('div');
    item.className = 'material-item';
    const icon = document.createElement('span');
    icon.className = 'm-icon';
    icon.textContent = '📄';
    const name = document.createElement('span');
    name.className = 'm-name';
    name.textContent = m.filename;
    name.title = m.filename;
    const chunks = document.createElement('span');
    chunks.className = 'm-chunks';
    chunks.textContent = `${m.chunks} 个分块`;
    item.appendChild(icon);
    item.appendChild(name);
    item.appendChild(chunks);
    els.materialList.appendChild(item);
  });
}

/* ---------- 资料上传 ---------- */
async function uploadMaterial(file) {
  if (!state.session) { toast('请先点击「新的学习」创建会话', 'error'); return; }
  if (state.streaming) { toast('请等待思小诘回复完成', 'error'); return; }

  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (!['.txt', '.md', '.pdf', '.docx'].includes(ext)) {
    toast('仅支持 .txt / .md / .pdf / .docx 文件', 'error');
    return;
  }

  // 列表中显示上传中 spinner
  const uploading = document.createElement('div');
  uploading.className = 'material-item';
  const sp = document.createElement('span');
  sp.className = 'spinner';
  const nm = document.createElement('span');
  nm.className = 'm-name';
  nm.textContent = file.name;
  const st = document.createElement('span');
  st.className = 'm-chunks';
  st.textContent = '上传中…';
  uploading.appendChild(sp);
  uploading.appendChild(nm);
  uploading.appendChild(st);
  els.materialList.appendChild(uploading);

  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`/api/materials?session_id=${state.session.id}`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    uploading.remove();
    state.materials.push(data.material);
    renderMaterials();
    if (Array.isArray(data.points)) {
      state.points = data.points;
      renderPoints();
    }
    if (data.replanned) toast('已根据资料更新学习计划', 'success');
    else toast('资料上传成功', 'success');
  } catch (e) {
    uploading.remove();
    toast('资料上传失败，请重试', 'error');
  }
}

/* ---------- 语音合成（TTS，排队依次播放） ---------- */
const ttsQueue = [];
let ttsBusy = false;
let currentAudio = null;

function speak(text) {
  if (!state.voiceOn || !text || !text.trim()) return;
  ttsQueue.push(text);
  pumpTts();
}

async function pumpTts() {
  if (ttsBusy) return;
  ttsBusy = true;
  while (ttsQueue.length) {
    const text = ttsQueue.shift();
    if (!state.voiceOn) continue; // 中途关闭则跳过剩余
    try {
      const res = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) continue; // 503 等失败静默跳过
      const blob = await res.blob();
      await playAudio(blob);
    } catch (e) { /* 单条失败继续下一条 */ }
  }
  ttsBusy = false;
}

function playAudio(blob) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    els.characterImg.classList.add('talking'); // 说话节奏动画
    const clean = () => {
      els.characterImg.classList.remove('talking');
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
      resolve();
    };
    audio.onended = clean;
    audio.onerror = clean;
    audio.play().catch(clean);
  });
}

function stopTts() {
  ttsQueue.length = 0;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
}

/* ---------- 启动 ---------- */
init();
