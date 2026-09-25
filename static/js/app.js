/* Edu-RAG-Tutor —— 前端逻辑（原生 JS，无依赖） */
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
  stageName: $('stage-name'),
  stageSub: $('stage-sub'),
  topicText: $('topic-text'),
  messageList: $('message-list'),
  chatInput: $('chat-input'),
  sendBtn: $('send-btn'),
  voiceInputBtn: $('voice-input-btn'),
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
  setThinking: $('set-thinking'),
  keyStatus: $('key-status'),
  toggleKeyBtn: $('toggle-key-btn'),
  testConnBtn: $('test-conn-btn'),
  testResult: $('test-result'),
  settingsCancel: $('settings-cancel'),
  settingsSave: $('settings-save'),
  clearKeyBtn: $('clear-key-btn'),
  charBubble: $('char-bubble'),
  focusBtn: $('focus-btn'),
  historyBtn: $('history-btn'),
  historyModal: $('history-modal'),
  historyClose: $('history-close'),
  methodModal: $('method-modal'),
  methodClose: $('method-close'),
  methodGrid: $('method-grid'),
  webSearchBtn: $('websearch-btn'),
  searchModal: $('search-modal'),
  searchClose: $('search-close'),
  searchInput: $('search-input'),
  searchGoBtn: $('search-go-btn'),
  typeChips: $('type-chips'),
  searchResults: $('search-results'),
  searchStatus: $('search-status'),
  // 学前测评弹窗
  assessModal: $('assess-modal'),
  assessClose: $('assess-close'),
  assessStepSetup: $('assess-step-setup'),
  assessTopic: $('assess-topic'),
  assessStartBtn: $('assess-start-btn'),
  assessStepQuiz: $('assess-step-quiz'),
  assessQuizHint: $('assess-quiz-hint'),
  assessQuizList: $('assess-quiz-list'),
  assessRequizBtn: $('assess-requiz-btn'),
  assessSubmitBtn: $('assess-submit-btn'),
  assessStepResult: $('assess-step-result'),
  assessTitle: $('assess-title'),
  // 错题本弹窗
  wrongbookBtn: $('wrongbook-btn'),
  wrongbookModal: $('wrongbook-modal'),
  wrongbookClose: $('wrongbook-close'),
  wrongbookStats: $('wrongbook-stats'),
  wrongbookList: $('wrongbook-list'),
  wrongbookPracticeBtn: $('wrongbook-practice-btn'),
  wrongbookExitBtn: $('wrongbook-exit-btn'),
};

/* ---------- 全局状态 ---------- */
const state = {
  session: null,       // 当前会话 {id, topic, status, method, progress...}
  phase: 'planning',   // 当前阶段
  emotion: 'idle',     // 当前立绘表情
  points: [],          // 知识点
  materials: [],       // 学习资料
  messages: [],        // 当前会话消息
  currentPointId: null,
  progress: 0,
  streaming: false,  // 是否正在接收 SSE 流
  voiceOn: localStorage.getItem('eduragtutor_voice') !== '0', // 语音默认开
  llmReady: false,   // 大模型 API 是否已配置（有 Key）
  // 学习方法系统：method=当前方法对象（含人物/表情图回退映射），methods=后端清单
  method: null,
  methods: [],
  // 联网找资料：searchType=类型筛选，searchQuery=上次搜索词，downloadingUrl=防重复下载
  searchType: 'all',
  searchQuery: '',
  downloadingUrl: null,
  // 专注模式：开启后隐藏左侧形象面板（本地持久化）
  focusOn: localStorage.getItem('eduragtutor_focus') === '1',
  // 学前测评 / 阶段自测：当前流程 {kind: 'assessment'|'phase', id, sessionId, topic, questions, answers}
  assess: null,
  // 阶段自测：quizSuggested=已提醒过自测的 mastered 知识点 id 集合（防重复弹卡）
  quizSuggested: new Set(),
  // 错题本：items/stats=服务端数据，practiceMode=重练作答中，answers={错题id: 所选下标}
  wrongbook: {
    items: [],
    stats: { total: 0, unresolved: 0, resolved: 0 },
    practiceMode: false,
    answers: {},
  },
};

/* ---------- 初始化 ---------- */
function init() {
  bindEvents();
  applyVoiceUI();
  applyFocusUI(); // 专注模式（本地持久化，启动即恢复）
  showWelcome();
  renderMaterials();
  loadSessions();
  loadSettings(); // 读取配置+音色；未配置 API Key 时弹出首启向导
  loadMethods().then(() => applyCharacter(findMethod(lastMethodId()))); // 恢复上次人物
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
  els.newSessionBtn.addEventListener('click', () => { closeHistory(); openMethodModal(); });
  els.settingsBtn.addEventListener('click', () => openSettings(false));
  els.characterImg.addEventListener('click', pokeCharacter); // 点击立绘互动

  // 主立绘加载失败兜底：切回 default 同名表情（打标防死循环）
  els.characterImg.addEventListener('error', () => {
    if (els.characterImg.dataset.fallback) return;
    els.characterImg.dataset.fallback = '1';
    els.characterImg.src = `assets/character/default/${state.emotion}.png`;
  });
  els.characterImg.addEventListener('load', () => { delete els.characterImg.dataset.fallback; });

  // 专注模式：隐藏左侧形象面板
  els.focusBtn.addEventListener('click', toggleFocus);
  // 历史学习弹窗
  els.historyBtn.addEventListener('click', openHistory);
  els.historyClose.addEventListener('click', closeHistory);
  els.historyModal.addEventListener('click', (ev) => {
    if (ev.target === els.historyModal) closeHistory();
  });

  // 学习方法选择弹窗
  els.methodClose.addEventListener('click', closeMethodModal);
  els.methodModal.addEventListener('click', (ev) => {
    if (ev.target === els.methodModal) closeMethodModal();
  });

  // 学前测评弹窗
  els.assessClose.addEventListener('click', closeAssessModal);
  els.assessModal.addEventListener('click', (ev) => {
    if (ev.target === els.assessModal) closeAssessModal();
  });
  els.assessStartBtn.addEventListener('click', startAssessment);
  els.assessTopic.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); startAssessment(); }
  });
  els.assessSubmitBtn.addEventListener('click', submitAssessment);
  els.assessRequizBtn.addEventListener('click', startAssessment);

  // 错题本弹窗
  els.wrongbookBtn.addEventListener('click', openWrongbook);
  els.wrongbookClose.addEventListener('click', closeWrongbook);
  els.wrongbookModal.addEventListener('click', (ev) => {
    if (ev.target === els.wrongbookModal) closeWrongbook();
  });
  els.wrongbookPracticeBtn.addEventListener('click', () => {
    if (state.wrongbook.practiceMode) submitPractice();
    else startPractice();
  });
  els.wrongbookExitBtn.addEventListener('click', exitPracticeMode);
  // 列表事件委托：「已掌握，移出待练」按钮
  els.wrongbookList.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.wrong-resolve-btn');
    if (btn) resolveWrong(Number(btn.dataset.id));
  });

  // 联网找资料弹窗
  els.webSearchBtn.addEventListener('click', openSearchModal);
  els.searchClose.addEventListener('click', closeSearchModal);
  els.searchModal.addEventListener('click', (ev) => {
    if (ev.target === els.searchModal) closeSearchModal();
  });
  els.searchGoBtn.addEventListener('click', performSearch);
  els.searchInput.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); performSearch(); }
  });
  els.typeChips.addEventListener('click', (ev) => {
    const chip = ev.target.closest('.chip');
    if (!chip) return;
    els.typeChips.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');
    state.searchType = chip.dataset.type;
    if (state.searchQuery) performSearch(); // 已有搜索词：切类型立即重搜
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

  // 输入栏 🎤 语音输入；右侧资料面板 label 仍用同一个 materialInput 文件选择器
  els.voiceInputBtn.addEventListener('click', toggleVoiceInput);
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

/* ---------- 语音输入（🎤 离线识别：前端录音 → /api/asr → 填入输入框） ---------- */
const voiceInput = {
  state: 'idle',        // idle | recording | processing
  stream: null,         // getUserMedia 媒体流
  audioCtx: null,
  processor: null,
  sourceNode: null,
  chunks: [],           // Float32Array 分片
  sampleRate: 16000,
  timeoutId: null,
  MAX_MS: 60000,        // 单次录音上限
};

async function toggleVoiceInput() {
  if (voiceInput.state === 'recording') { stopVoiceInput(); return; }
  if (voiceInput.state !== 'idle' || state.streaming) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    toast('当前环境不支持麦克风录音，请用系统浏览器打开应用使用', 'error');
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: voiceInput.sampleRate, channelCount: 1, echoCancellation: true },
    });
  } catch (e) {
    toast('无法访问麦克风：请检查系统/应用麦克风权限（安装版可改用浏览器模式）', 'error');
    return;
  }
  voiceInput.state = 'recording';
  voiceInput.stream = stream;
  voiceInput.chunks = [];
  voiceInput.audioCtx = new AudioContext({ sampleRate: voiceInput.sampleRate });
  voiceInput.sourceNode = voiceInput.audioCtx.createMediaStreamSource(stream);
  voiceInput.processor = voiceInput.audioCtx.createScriptProcessor(4096, 1, 1);
  voiceInput.processor.onaudioprocess = (ev) => {
    voiceInput.chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
  };
  voiceInput.sourceNode.connect(voiceInput.processor);
  voiceInput.processor.connect(voiceInput.audioCtx.destination); // 驱动回调（不输出声音）
  els.voiceInputBtn.classList.add('recording');
  els.voiceInputBtn.title = '正在录音，点击结束';
  els.chatInput.placeholder = '正在听你说话…说完点击 🎤 结束';
  voiceInput.timeoutId = setTimeout(stopVoiceInput, voiceInput.MAX_MS); // 超长自动结束
}

function stopVoiceInput() {
  if (voiceInput.state !== 'recording') return;
  voiceInput.state = 'processing';
  clearTimeout(voiceInput.timeoutId);
  els.voiceInputBtn.classList.remove('recording');
  els.voiceInputBtn.classList.add('processing');
  els.voiceInputBtn.title = '识别中…';
  els.chatInput.placeholder = '正在识别…';

  try { voiceInput.processor && voiceInput.processor.disconnect(); } catch (e) { /* 忽略 */ }
  try { voiceInput.sourceNode && voiceInput.sourceNode.disconnect(); } catch (e) { /* 忽略 */ }
  voiceInput.stream && voiceInput.stream.getTracks().forEach((t) => t.stop());
  const ctx = voiceInput.audioCtx;
  const pcm = mergeChunks(voiceInput.chunks);
  voiceInput.audioCtx = null; voiceInput.processor = null; voiceInput.sourceNode = null;
  voiceInput.stream = null; voiceInput.chunks = [];

  const finish = () => {
    voiceInput.state = 'idle';
    els.voiceInputBtn.classList.remove('processing');
    els.voiceInputBtn.title = '语音输入：点击开始，说完再点一次结束';
    updateInputPlaceholder();
  };
  if (ctx && ctx.state !== 'closed') ctx.close().catch(() => {});
  const total = pcm.length / voiceInput.sampleRate;
  if (total < 0.5) { toast('说话时间太短了，再试一次吧', 'error'); finish(); return; }

  const blob = encodeWav(pcm, voiceInput.sampleRate);
  fetch('/api/asr', { method: 'POST', body: blob })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(asrErrText(data, res));
      const text = (data.text || '').trim();
      if (!text) { toast('没听清你说什么，再试一次吧', 'error'); return; }
      els.chatInput.value = els.chatInput.value
        ? `${els.chatInput.value.trimEnd()}${text}`
        : text;
      autoResizeInput();
      els.chatInput.focus();
    })
    .catch((e) => {
      const msg = String(e.message || '');
      if (msg.includes('模型未配置')) toast('语音识别模型未配置：按 语音包说明.txt 下载后放入 models/asr/', 'error');
      else toast(`语音识别失败：${msg}`, 'error');
    })
    .finally(finish);
}

/* 从 /api/asr 错误响应里取人话（detail 可能是字符串，也可能是校验错误数组） */
function asrErrText(data, res) {
  const d = data && data.detail;
  if (typeof d === 'string' && d) return d;
  if (Array.isArray(d)) {
    const msgs = d.map((x) => (x && x.msg) || '').filter(Boolean).join('；');
    if (msgs) return msgs;
  }
  return `HTTP ${res ? res.status : '?'}`;
}

/* 合并 Float32 分片 */
function mergeChunks(chunks) {
  let len = 0;
  chunks.forEach((c) => { len += c.length; });
  const out = new Float32Array(len);
  let off = 0;
  chunks.forEach((c) => { out.set(c, off); off += c.length; });
  return out;
}

/* Float32 PCM → 16bit 单声道 WAV Blob（RIFF 头） */
function encodeWav(samples, sampleRate) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);          // fmt 块大小
  view.setUint16(20, 1, true);           // PCM
  view.setUint16(22, 1, true);           // 单声道
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);  // 字节率
  view.setUint16(32, 2, true);           // 块对齐
  view.setUint16(34, 16, true);          // 位深
  writeStr(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return new Blob([view], { type: 'audio/wav' });
}

/* ---------- 语音开关 ---------- */
function toggleVoice() {
  state.voiceOn = !state.voiceOn;
  localStorage.setItem('eduragtutor_voice', state.voiceOn ? '1' : '0');
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
  localStorage.setItem('eduragtutor_focus', state.focusOn ? '1' : '0');
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

/* ---------- 学习方法与人物形象 ---------- */
function lastMethodId() {
  return localStorage.getItem('eduragtutor_method') || 'socratic';
}

/* 当前人物名（清单未加载时兜底思小诘） */
function charName() {
  return (state.method && state.method.char_name) || '思小诘';
}

/* 按当前方法取表情图路径（后端 resolved 已逐表情回退 default，这里再兜底一层） */
function charAsset(emotion) {
  const m = state.method;
  if (m && m.resolved && m.resolved[emotion]) return m.resolved[emotion];
  return `assets/character/default/${emotion}.png`;
}

/* 拉取学习方法清单（force=每次现拉，支持热放图） */
async function loadMethods(force = false) {
  if (state.methods.length && !force) return state.methods;
  try {
    const res = await fetch('/api/methods');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.methods = data.methods || [];
  } catch (e) { /* 失败保留空清单，charAsset 有兜底 */ }
  return state.methods;
}

function findMethod(id) {
  return state.methods.find((m) => m.id === id) || state.methods[0] || null;
}

/* 应用人物：更新方法态 → 名字/头衔/立绘 → 预加载表情 → 刷新输入框提示 */
function applyCharacter(methodObj) {
  if (methodObj) state.method = methodObj;
  els.stageName.textContent = charName();
  els.stageSub.textContent = (state.method && state.method.char_title) || '你的学习伙伴';
  els.characterImg.alt = `${charName()}立绘`;
  els.characterImg.src = charAsset(state.emotion);
  EMOTIONS.forEach((e) => { const img = new Image(); img.src = charAsset(e); }); // 预加载
  updateInputPlaceholder();
}

/* 输入框提示随人物变化 */
function updateInputPlaceholder() {
  if (!state.streaming) {
    els.chatInput.placeholder = `和${charName()}聊聊你想学什么…（Enter 发送，Shift+Enter 换行）`;
  }
}

/* ---------- 学习方法选择弹窗 ---------- */
async function openMethodModal() {
  await loadMethods(true); // 每次打开现拉，热放图立即生效
  renderMethodCards();
  els.methodModal.classList.remove('hidden');
}

function closeMethodModal() {
  els.methodModal.classList.add('hidden');
}

/* 渲染方法卡片网格（头像取 resolved.idle，无专属图时即 default 图） */
function renderMethodCards() {
  els.methodGrid.innerHTML = '';
  renderAssessCard(); // 固定在首位的"学前测评"入口卡
  state.methods.forEach((m) => {
    const card = document.createElement('div');
    card.className = 'method-card';
    card.dataset.id = m.id;
    card.title = m.name;

    const av = document.createElement('img');
    av.className = 'm-avatar';
    av.alt = m.char_name;
    av.src = (m.resolved && m.resolved.idle) || `assets/character/default/idle.png`;

    const body = document.createElement('div');
    body.className = 'm-body';
    const title = document.createElement('div');
    title.className = 'm-title';
    title.textContent = `${m.emoji || ''} ${m.name}`.trim();
    const char = document.createElement('div');
    char.className = 'm-char';
    char.textContent = `伙伴：${m.char_name}`;
    if (!m.has_own_assets) {
      const tag = document.createElement('span');
      tag.className = 'm-asset-tag';
      tag.textContent = '形象待放入';
      tag.title = '把人物图片放入对应 character 目录即可显示专属形象';
      char.appendChild(tag);
    }
    const intro = document.createElement('div');
    intro.className = 'm-intro';
    intro.textContent = m.intro || '';
    body.appendChild(title);
    body.appendChild(char);
    body.appendChild(intro);

    // 试听按钮：阻止冒泡，避免触发卡片的"选择该方法"
    const voiceBtn = document.createElement('button');
    voiceBtn.className = 'mini-btn m-voice';
    voiceBtn.type = 'button';
    voiceBtn.textContent = '🔊 试听';
    if (m.voice) voiceBtn.title = `音色：${m.voice}${m.voice_custom ? '（自定义语音包）' : ''}`;
    voiceBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      previewMethodVoice(m, voiceBtn);
    });

    card.appendChild(av);
    card.appendChild(body);
    card.appendChild(voiceBtn);
    card.addEventListener('click', () => selectMethod(m.id));
    els.methodGrid.appendChild(card);
  });
}

/* 选定方法 → 创建新学习会话 */
async function selectMethod(id) {
  els.methodGrid.classList.add('locked'); // 防双击重复建会话
  try {
    closeMethodModal();
    const s = await createSession(id);
    if (s) {
      const m = findMethod(id);
      toast(m ? `已开始「${m.name}」，伙伴：${m.char_name}` : '新学习已创建', 'success');
    }
  } finally {
    els.methodGrid.classList.remove('locked');
  }
}

/* ---------- 学前测评（摸底出题 → 答题 → 判分并规划路线） ---------- */

/* 固定在方法清单首位的测评入口卡 */
function renderAssessCard() {
  const card = document.createElement('div');
  card.className = 'method-card assess-card';
  card.title = '学前测评 · 定制学习路线';

  const av = document.createElement('div');
  av.className = 'm-avatar assess-avatar';
  av.textContent = '🧭';

  const body = document.createElement('div');
  body.className = 'm-body';
  const title = document.createElement('div');
  title.className = 'm-title';
  title.textContent = '🧭 学前测评';
  const sub = document.createElement('div');
  sub.className = 'm-char';
  sub.textContent = '先摸底，再定制学习路线';
  const intro = document.createElement('div');
  intro.className = 'm-intro';
  intro.textContent = '做约 10 道摸底选择题，判断掌握程度，规划"先学什么、再拿什么方法巩固"的多阶段路线';
  body.appendChild(title);
  body.appendChild(sub);
  body.appendChild(intro);

  card.appendChild(av);
  card.appendChild(body);
  card.addEventListener('click', () => {
    closeMethodModal();
    openAssessModal();
  });
  els.methodGrid.appendChild(card);
}

/* 打开测评弹窗（prefill=预填主题，如用户刚输入的话）；学前测评模式 */
function openAssessModal(prefill = '') {
  state.assess = { kind: 'assessment' };
  els.assessTitle.textContent = '🧭 学前测评';
  els.assessStepSetup.classList.remove('hidden');
  els.assessStepQuiz.classList.add('hidden');
  els.assessStepResult.classList.add('hidden');
  els.assessStepResult.innerHTML = '';
  if (prefill) els.assessTopic.value = prefill;
  els.assessModal.classList.remove('hidden');
  els.assessTopic.focus();
  loadMethods(); // 预载方法清单，路线阶段卡才能显示方法名与 emoji
}

function closeAssessModal() {
  els.assessModal.classList.add('hidden');
}

/* 第一步 → 第二步：请求出题（「换一套题」与阶段自测也走这里） */
async function startAssessment() {
  const isPhase = !!(state.assess && state.assess.kind === 'phase');
  const topic = isPhase ? (state.assess.topic || '') : els.assessTopic.value.trim();
  if (!isPhase && !topic) { toast('请先填写想学的主题', 'error'); return; }
  if (!state.llmReady) {
    toast('请先配置大模型 API（右上角 ⚙️）', 'error');
    closeAssessModal();
    openSettings(true);
    return;
  }
  els.assessStartBtn.disabled = true;
  els.assessStartBtn.textContent = '出题中…';
  els.assessRequizBtn.disabled = true;
  if (isPhase) {
    els.assessSubmitBtn.disabled = true;
    els.assessSubmitBtn.textContent = '出题中…';
  }
  let loaded = false;
  try {
    const res = await fetch(isPhase ? '/api/quiz' : '/api/assessment/quiz', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(isPhase ? { session_id: state.assess.sessionId } : { topic }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.status);
    state.assess = {
      kind: isPhase ? 'phase' : 'assessment',
      id: data.id,
      sessionId: isPhase ? state.assess.sessionId : null,
      topic: isPhase ? (data.topic || topic) : topic,
      questions: data.questions || [],
      answers: [],
    };
    renderQuiz();
    loaded = true;
  } catch (e) {
    toast(`出题失败：${e.message || '请稍后重试'}`, 'error');
    if (isPhase) closeAssessModal();
  } finally {
    els.assessStartBtn.disabled = false;
    els.assessStartBtn.textContent = '开始出题 ✨';
    els.assessRequizBtn.disabled = false;
    els.assessSubmitBtn.disabled = false; // 出题失败时还原交卷按钮；成功时由 renderQuiz 解禁、updateQuizProgress 管文案
    if (!loaded) els.assessSubmitBtn.textContent = '交卷看结果';
  }
}

/* 渲染答题区（题目由易到难，单选；阶段自测复用同一答题区） */
function renderQuiz() {
  const qs = state.assess.questions;
  const isPhase = state.assess.kind === 'phase';
  state.assess.answers = new Array(qs.length).fill(-1);
  els.assessStepSetup.classList.add('hidden');
  els.assessStepResult.classList.add('hidden');
  els.assessStepResult.innerHTML = '';
  els.assessStepQuiz.classList.remove('hidden');
  els.assessQuizHint.textContent = isPhase
    ? `主题「${state.assess.topic}」· 针对你已学过的知识点出了 ${qs.length} 道单选题。做错的题会自动收进错题本，随时可重练～`
    : `主题「${state.assess.topic}」共 ${qs.length} 道单选题（由易到难）。凭现有理解作答即可，摸底只是分档，答错不影响开始学习～`;
  els.assessRequizBtn.classList.toggle('hidden', isPhase); // 阶段自测无"换一套题"
  els.assessQuizList.innerHTML = '';
  qs.forEach((q, qi) => {
    const item = document.createElement('div');
    item.className = 'quiz-item';
    const title = document.createElement('div');
    title.className = 'quiz-q';
    const tag = document.createElement('span');
    tag.className = 'quiz-tag';
    tag.textContent = q.difficulty === 'easy' ? '易' : q.difficulty === 'hard' ? '难' : '中';
    title.appendChild(tag);
    title.appendChild(document.createTextNode(`${qi + 1}. ${q.question}`));
    item.appendChild(title);

    const opts = document.createElement('div');
    opts.className = 'quiz-opts';
    q.options.forEach((opt, oi) => {
      const label = document.createElement('label');
      label.className = 'quiz-opt';
      const input = document.createElement('input');
      input.type = 'radio';
      input.name = `quiz-${qi}`;
      input.addEventListener('change', () => {
        state.assess.answers[qi] = oi;
        updateQuizProgress();
      });
      label.appendChild(input);
      const span = document.createElement('span');
      span.textContent = `${'ABCD'[oi]}. ${opt}`;
      label.appendChild(span);
      opts.appendChild(label);
    });
    item.appendChild(opts);
    els.assessQuizList.appendChild(item);
  });
  els.assessSubmitBtn.disabled = false; // 出题成功：交卷按钮解除"出题中…"的禁用态
  updateQuizProgress();
  els.assessModal.scrollTop = 0;
}

function updateQuizProgress() {
  const done = state.assess.answers.filter((a) => a >= 0).length;
  els.assessSubmitBtn.textContent =
    done >= state.assess.questions.length ? '交卷看结果' : `已答 ${done}/${state.assess.questions.length}`;
}

/* 第二步 → 第三步：交卷 → 本地判分（学前测评另规划路线；阶段自测错题入本） */
async function submitAssessment() {
  const unanswered = state.assess.answers.filter((a) => a < 0).length;
  if (unanswered > 0) { toast(`还有 ${unanswered} 题没作答哦`, 'error'); return; }
  const isPhase = state.assess.kind === 'phase';
  els.assessSubmitBtn.disabled = true;
  els.assessSubmitBtn.textContent = isPhase ? '判分中…' : '判分规划中…';
  try {
    const res = await fetch(isPhase ? '/api/quiz/submit' : '/api/assessment/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        isPhase
          ? { quiz_id: state.assess.id, answers: state.assess.answers }
          : { assessment_id: state.assess.id, answers: state.assess.answers }
      ),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.status);
    renderAssessResult(data);
    if (isPhase) {
      const wrong = (data.total || 0) - (data.score || 0);
      if (wrong > 0) toast(`${wrong} 道错题已收进错题本 📒`, 'success');
    }
  } catch (e) {
    toast(`提交失败：${e.message || '请稍后重试'}`, 'error');
  } finally {
    els.assessSubmitBtn.disabled = false;
    updateQuizProgress();
  }
}

/* 渲染结果：得分 + 逐题复盘（学前测评→多阶段学习路线；阶段自测→错题本提示） */
function renderAssessResult(result) {
  const isPhase = !!(state.assess && state.assess.kind === 'phase');
  els.assessStepQuiz.classList.add('hidden');
  const box = els.assessStepResult;
  box.innerHTML = '';
  box.classList.remove('hidden');

  const head = document.createElement('div');
  head.className = 'assess-head';
  head.textContent = isPhase
    ? `📊 阶段自测：${result.score}/${result.total}`
    : `📊 摸底结果：${result.score}/${result.total} · ${result.level || ''}`;
  box.appendChild(head);

  if (result.summary) {
    const p = document.createElement('p');
    p.className = 'assess-summary';
    p.textContent = result.summary;
    box.appendChild(p);
  }

  const review = document.createElement('div');
  review.className = 'assess-review';
  result.questions.forEach((q, qi) => {
    const ok = result.answers[qi] === q.answer;
    const row = document.createElement('div');
    row.className = `review-item ${ok ? 'ok' : 'bad'}`;
    const line1 = document.createElement('div');
    line1.className = 'review-q';
    line1.textContent = `${ok ? '✅' : '❌'} ${qi + 1}. ${q.question}`;
    row.appendChild(line1);
    if (!ok) {
      const line2 = document.createElement('div');
      line2.className = 'review-a';
      line2.textContent =
        `正确答案：${'ABCD'[q.answer]}. ${q.options[q.answer]}` +
        (q.explanation ? `　—　${q.explanation}` : '');
      row.appendChild(line2);
    }
    review.appendChild(row);
  });
  box.appendChild(review);

  if (isPhase) {
    // 阶段自测：错题去向提示 + 错题本入口（无路线规划）
    const wrong = (result.total || 0) - (result.score || 0);
    const p = document.createElement('p');
    p.className = 'assess-summary';
    p.textContent = wrong > 0
      ? `❌ ${wrong} 道做错的题已收进错题本，右上角 📒 随时可以重练，练到掌握为止～`
      : '全对，太棒了！继续保持 ✨';
    box.appendChild(p);
    if (wrong > 0) {
      const actRow = document.createElement('div');
      actRow.className = 'modal-actions';
      const openBtn = document.createElement('button');
      openBtn.className = 'mini-btn';
      openBtn.type = 'button';
      openBtn.textContent = '打开错题本 📒';
      openBtn.addEventListener('click', () => { closeAssessModal(); openWrongbook(); });
      actRow.appendChild(openBtn);
      box.appendChild(actRow);
    }
  } else {
    const routeTitle = document.createElement('div');
    routeTitle.className = 'assess-head';
    routeTitle.textContent = '🗺️ 你的学习路线';
    box.appendChild(routeTitle);

    const route = result.route || [];
    if (!route.length) {
      const p = document.createElement('p');
      p.className = 'assess-summary';
      p.textContent = '路线规划这次没有生成成功，你可以直接点「＋ 新的学习」挑一种方法开始，摸底结果同样作数～';
      box.appendChild(p);
    }
    route.forEach((phase, pi) => {
      const m = findMethod(phase.method);
      const card = document.createElement('div');
      card.className = 'route-phase';

      const t = document.createElement('div');
      t.className = 'route-title';
      t.textContent = `第 ${pi + 1} 阶段 · ${m ? `${m.emoji} ${m.name}` : phase.method}`;
      card.appendChild(t);

      if (phase.goal) {
        const g = document.createElement('div');
        g.className = 'route-goal';
        g.textContent = phase.goal;
        card.appendChild(g);
      }
      if (phase.points && phase.points.length) {
        const pts = document.createElement('div');
        pts.className = 'route-points';
        pts.textContent = `聚焦：${phase.points.join('、')}`;
        card.appendChild(pts);
      }
      if (phase.milestone) {
        const ms = document.createElement('div');
        ms.className = 'route-milestone';
        ms.textContent = `🏁 达标即切换：${phase.milestone}`;
        card.appendChild(ms);
      }

      const btn = document.createElement('button');
      btn.className = pi === 0 ? 'primary-btn' : 'mini-btn';
      btn.type = 'button';
      btn.textContent = pi === 0 ? `🚀 用${m ? m.name : '该方法'}开始学习` : `从第 ${pi + 1} 阶段开始`;
      btn.addEventListener('click', () => startFromRoute(phase, pi));
      card.appendChild(btn);
      box.appendChild(card);
    });
  }

  const closeRow = document.createElement('div');
  closeRow.className = 'modal-actions';
  const sp = document.createElement('span');
  sp.className = 'sp';
  closeRow.appendChild(sp);
  const done = document.createElement('button');
  done.className = 'mini-btn';
  done.type = 'button';
  done.textContent = '完成';
  done.addEventListener('click', closeAssessModal);
  closeRow.appendChild(done);
  box.appendChild(closeRow);
  els.assessModal.scrollTop = 0;
}

/* 从路线阶段开始学习：按该阶段方法建会话，主题作为第一条消息发出 */
async function startFromRoute(phase, phaseIndex) {
  const m = findMethod(phase.method);
  const topic = (state.assess && state.assess.topic) || '';
  closeAssessModal();
  const session = await createSession(phase.method);
  if (!session) return;
  toast(m ? `已按路线从第 ${phaseIndex + 1} 阶段出发：「${m.name}」` : '新学习已创建', 'success');
  if (topic) {
    renderMessage('user', topic);
    streamChat(topic);
  }
}

/* ---------- 阶段自测：建议卡（知识点新变为"已掌握"时提醒） ---------- */
/* SSE state 事件后调用：diff 出新掌握的知识点，每点只提醒一次 */
function checkPhaseQuiz(points) {
  if (!state.session || !Array.isArray(points)) return;
  const fresh = points.filter((p) => p.status === 'mastered' && !state.quizSuggested.has(p.id));
  if (!fresh.length) return;
  fresh.forEach((p) => state.quizSuggested.add(p.id));
  showQuizSuggestion(fresh);
}

/* 在聊天流里插一张自测建议卡（一次回复完成多点时合并为一张卡） */
function showQuizSuggestion(points) {
  const card = document.createElement('div');
  card.className = 'system-card assess-suggest';

  const p = document.createElement('div');
  p.className = 'suggest-text';
  const names = points.map((x) => x.name).join('、');
  p.textContent =
    `🎉 恭喜拿下「${names}」！要不要来一场 📝 阶段自测？` +
    '针对刚学的内容出几道小题检验一下，做错的题会自动收进错题本，随时可重练～';
  card.appendChild(p);

  const row = document.createElement('div');
  row.className = 'suggest-actions';
  const goBtn = document.createElement('button');
  goBtn.className = 'primary-btn';
  goBtn.type = 'button';
  goBtn.textContent = '开始自测';
  goBtn.addEventListener('click', openPhaseQuizModal);
  const laterBtn = document.createElement('button');
  laterBtn.className = 'mini-btn';
  laterBtn.type = 'button';
  laterBtn.textContent = '稍后再说';
  laterBtn.addEventListener('click', () => card.remove());
  row.appendChild(goBtn);
  row.appendChild(laterBtn);
  card.appendChild(row);

  els.messageList.appendChild(card);
  scrollToBottom();
}

/* 打开阶段自测弹窗：复用测评弹窗，跳过主题输入直接出题 */
async function openPhaseQuizModal() {
  if (!state.session) { toast('当前没有进行中的学习会话', 'error'); return; }
  if (!state.llmReady) {
    toast('请先配置大模型 API（右上角 ⚙️）', 'error');
    openSettings(true);
    return;
  }
  state.assess = { kind: 'phase', sessionId: state.session.id, topic: state.session.topic || '' };
  els.assessTitle.textContent = '📝 阶段自测';
  els.assessStepSetup.classList.add('hidden');
  els.assessStepResult.classList.add('hidden');
  els.assessStepResult.innerHTML = '';
  els.assessQuizList.innerHTML = '';
  els.assessStepQuiz.classList.remove('hidden');
  els.assessQuizHint.textContent = '正在针对你已学过的知识点出题…';
  els.assessModal.classList.remove('hidden');
  await startAssessment();
}

/* ---------- 错题本 ---------- */
async function openWrongbook() {
  els.wrongbookModal.classList.remove('hidden');
  els.wrongbookStats.textContent = '加载中…';
  els.wrongbookPracticeBtn.disabled = true;
  await fetchWrongbook();
}

function closeWrongbook() {
  state.wrongbook.practiceMode = false;
  state.wrongbook.answers = {};
  els.wrongbookModal.classList.add('hidden');
}

async function fetchWrongbook() {
  try {
    const res = await fetch('/api/wrongbook');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.wrongbook.items = data.items || [];
    state.wrongbook.stats = data.stats || { total: 0, unresolved: 0, resolved: 0 };
    state.wrongbook.practiceMode = false;
    state.wrongbook.answers = {};
    renderWrongbook();
  } catch (e) {
    toast('错题本加载失败，请稍后重试', 'error');
  }
}

/* 渲染错题列表：普通模式（看题+标掌握）/ 重练模式（待掌握的题可作答） */
function renderWrongbook() {
  const wb = state.wrongbook;
  const st = wb.stats || { total: 0, unresolved: 0, resolved: 0 };
  els.wrongbookStats.textContent = `共 ${st.total} 题 · 🔴 待掌握 ${st.unresolved} · 🟢 已掌握 ${st.resolved}`;
  els.wrongbookList.innerHTML = '';

  if (!wb.items.length) {
    const p = document.createElement('p');
    p.className = 'panel-hint';
    p.textContent = '暂无错题，继续保持！🎉';
    els.wrongbookList.appendChild(p);
  } else {
    wb.items.forEach((w) => {
      const item = document.createElement('div');
      item.className = `wrong-item quiz-item${w.resolved ? ' is-resolved' : ''}`;

      const title = document.createElement('div');
      title.className = 'quiz-q';
      const badge = document.createElement('span');
      badge.className = `badge ${w.resolved ? 'mastered' : 'weak'}`;
      badge.textContent = w.resolved ? '已掌握' : `待掌握 · 错${w.wrong_count || 1}次`;
      title.appendChild(badge);
      title.appendChild(document.createTextNode(w.question || ''));
      item.appendChild(title);

      const opts = document.createElement('div');
      opts.className = 'wrong-opts';
      if (wb.practiceMode && !w.resolved) {
        // 重练模式：待掌握的题渲染为可作答单选
        (w.options || []).forEach((opt, oi) => {
          const label = document.createElement('label');
          label.className = 'quiz-opt';
          const input = document.createElement('input');
          input.type = 'radio';
          input.name = `wrong-${w.id}`;
          input.addEventListener('change', () => {
            wb.answers[w.id] = oi;
            updatePracticeProgress();
          });
          label.appendChild(input);
          const span = document.createElement('span');
          span.textContent = `${'ABCD'[oi]}. ${opt}`;
          label.appendChild(span);
          opts.appendChild(label);
        });
      } else {
        // 普通/反馈模式：静态展示选项，✔ 正确答案、✘ 你最近错选
        (w.options || []).forEach((opt, oi) => {
          const line = document.createElement('div');
          const isAnswer = oi === w.answer;
          const isUser = !isAnswer && oi === w.user_answer;
          line.className = `wrong-opt${isAnswer ? ' is-answer' : ''}${isUser ? ' is-user' : ''}`;
          line.textContent = `${isAnswer ? '✔ ' : isUser ? '✘ ' : ''}${'ABCD'[oi]}. ${opt}`;
          opts.appendChild(line);
        });
      }
      item.appendChild(opts);

      // 重练反馈（本轮刚判分）
      if (w.last_practice_ok !== undefined) {
        const fb = document.createElement('div');
        fb.className = 'wrong-feedback';
        fb.textContent = w.last_practice_ok
          ? '✅ 答对了，这题已自动标记为已掌握！'
          : `❌ 又错了：正确答案是 ${'ABCD'[w.answer] || ''}.${(w.options || [])[w.answer] || ''}` +
            (w.explanation ? `　—　${w.explanation}` : '');
        fb.classList.add(w.last_practice_ok ? 'ok' : 'bad');
        item.appendChild(fb);
      }

      // 来源行：类型 · 学伴 · 主题 · 考察点
      const meta = document.createElement('div');
      meta.className = 'wrong-meta';
      const src = w.source === 'assessment' ? '学前测评' : '阶段自测';
      const parts = [src];
      if (w.method_label) parts.push(w.method_label);
      if (w.topic) parts.push(`「${w.topic}」`);
      if (w.point) parts.push(`考察：${w.point}`);
      meta.textContent = parts.join(' · ');
      item.appendChild(meta);

      // 普通模式下未解决的题：手动标已掌握
      if (!wb.practiceMode && !w.resolved) {
        const btn = document.createElement('button');
        btn.className = 'mini-btn wrong-resolve-btn';
        btn.type = 'button';
        btn.dataset.id = w.id;
        btn.textContent = '已掌握，移出待练';
        item.appendChild(btn);
      }
      els.wrongbookList.appendChild(item);
    });
  }

  // 底部按钮状态
  if (wb.practiceMode) {
    els.wrongbookPracticeBtn.disabled = false;
    els.wrongbookExitBtn.classList.remove('hidden');
    updatePracticeProgress();
  } else {
    els.wrongbookPracticeBtn.textContent = '✏️ 错题重练';
    els.wrongbookPracticeBtn.disabled = st.unresolved === 0;
    els.wrongbookExitBtn.classList.add('hidden');
  }
}

/* 重练模式：提交按钮文案随作答进度变化 */
function updatePracticeProgress() {
  if (!state.wrongbook.practiceMode) return;
  const targets = state.wrongbook.items.filter((w) => !w.resolved);
  const done = targets.filter((w) => state.wrongbook.answers[w.id] !== undefined).length;
  els.wrongbookPracticeBtn.textContent =
    done >= targets.length ? '交卷看结果' : `已答 ${done}/${targets.length}`;
}

/* 进入重练：清掉旧反馈，待掌握的题变可作答 */
function startPractice() {
  const wb = state.wrongbook;
  const targets = wb.items.filter((w) => !w.resolved);
  if (!targets.length) { toast('没有待重练的错题', 'info'); return; }
  wb.items.forEach((w) => { delete w.last_practice_ok; });
  wb.answers = {};
  wb.practiceMode = true;
  renderWrongbook();
}

/* 退出重练：回到普通列表（清作答与反馈） */
function exitPracticeMode() {
  const wb = state.wrongbook;
  wb.practiceMode = false;
  wb.answers = {};
  wb.items.forEach((w) => { delete w.last_practice_ok; });
  renderWrongbook();
}

/* 交卷：判分 + 答对自动已掌握 / 答错 wrong_count+1，本地同步状态并渲染反馈 */
async function submitPractice() {
  const wb = state.wrongbook;
  const targets = wb.items.filter((w) => !w.resolved);
  const answers = targets.map((w) => ({ id: w.id, choice: wb.answers[w.id] }));
  const unanswered = answers.filter((a) => a.choice === undefined).length;
  if (unanswered > 0) { toast(`还有 ${unanswered} 题没作答哦`, 'error'); return; }
  els.wrongbookPracticeBtn.disabled = true;
  els.wrongbookPracticeBtn.textContent = '判分中…';
  try {
    const res = await fetch('/api/wrongbook/practice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.status);
    (data.results || []).forEach((r) => {
      const w = wb.items.find((x) => x.id === r.id);
      if (!w) return;
      w.last_practice_ok = !!r.ok;
      if (r.ok) w.resolved = 1;
      else {
        w.wrong_count = (w.wrong_count || 1) + 1;
        w.user_answer = r.choice;
      }
    });
    const resolvedCount = data.resolved_count || 0;
    wb.stats.resolved = (wb.stats.resolved || 0) + resolvedCount;
    wb.stats.unresolved = Math.max(0, (wb.stats.unresolved || 0) - resolvedCount);
    wb.practiceMode = false;
    wb.answers = {};
    renderWrongbook();
    toast(
      resolvedCount > 0
        ? `答对 ${resolvedCount} 题，已自动标记掌握 ✨`
        : '这次还差一点，看看解析再来一次，你可以的！',
      resolvedCount > 0 ? 'success' : 'info'
    );
  } catch (e) {
    toast(`重练提交失败：${e.message || '请稍后重试'}`, 'error');
    renderWrongbook(); // 回到重练模式（恢复按钮与作答状态）
  }
}

/* 手动把错题标为已掌握 */
async function resolveWrong(id) {
  if (!id) return;
  try {
    const res = await fetch('/api/wrongbook/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) throw new Error(res.status);
    const wb = state.wrongbook;
    const w = wb.items.find((x) => x.id === id);
    if (w && !w.resolved) {
      w.resolved = 1;
      wb.stats.resolved = (wb.stats.resolved || 0) + 1;
      wb.stats.unresolved = Math.max(0, (wb.stats.unresolved || 0) - 1);
    }
    renderWrongbook();
  } catch (e) {
    toast('操作失败，请稍后重试', 'error');
  }
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
const DEFAULT_QUIPS = [
  '嘿嘿，被你点到啦～',
  '学习累了？让眼睛休息一下吧！',
  '今天想学点什么呀？',
  '小提示：上传资料能让学习计划更贴合你哦！',
  '偷偷告诉你：每天学一点，坚持最可怕！',
];

/* 点击立绘：随机表情 + 弹跳 + 当前人物专属俏皮话气泡（+语音朗读） */
function pokeCharacter() {
  const pool = EMOTIONS.filter((e) => e !== state.emotion);
  setEmotion(pool[Math.floor(Math.random() * pool.length)]);
  const quips = (state.method && state.method.quips && state.method.quips.length)
    ? state.method.quips : DEFAULT_QUIPS;
  const quip = quips[Math.floor(Math.random() * quips.length)];
  showCharBubble(quip);
  // 打断式播放：清掉积压的学习朗读队列，交互台词立即开口，
  // 否则新台词排在队尾，听到的还是之前积压的内容
  stopTts();
  speak(quip);
}

let bubbleTimer = null;
function showCharBubble(text) {
  els.charBubble.textContent = text;
  els.charBubble.classList.add('show');
  clearTimeout(bubbleTimer);
  // 时长须覆盖"清队+合成+开播"的延迟（约1~2s），避免声音还没响气泡就消失
  bubbleTimer = setTimeout(() => els.charBubble.classList.remove('show'), 4500);
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
    if (!data.configured) openSettings(true); // 首次使用 → 向导
  } catch (e) { /* 静默失败：聊天时还会兜底提示 */ }
}

function openSettings(wizard) {
  settingsWizard = wizard;
  // 预填当前生效的 base_url / model；Key 不回填，仅显示掩码状态
  fetch('/api/settings').then((r) => r.json()).then((data) => {
    els.setBaseUrl.value = data.base_url || '';
    els.setModel.value = data.model || '';
    els.setThinking.checked = !!data.thinking; // 深度思考开关（默认关=快速）
    els.keyStatus.textContent = data.configured ? `已配置 ${data.api_key_masked}` : '未配置';
    els.clearKeyBtn.classList.toggle('hidden', !data.configured);
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

/* 保存设置：Key 留空 = 保持不变；URL/模型留空 = 恢复默认 */
async function saveSettings() {
  const body = {
    api_key: els.setApiKey.value.trim(),
    base_url: els.setBaseUrl.value.trim(),
    model: els.setModel.value.trim(),
    thinking: els.setThinking.checked,
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
    closeSettings();
    toast(settingsWizard ? '配置完成，开始学习吧！' : '设置已保存', 'success');
  } catch (e) {
    toast('保存失败，请重试', 'error');
  } finally {
    els.settingsSave.disabled = false;
  }
}

/* 试听学伴音色（方法选择卡片）：临时音色直接合成播放，无需保存 */
async function previewMethodVoice(m, btn) {
  if (!m || !m.voice) return;
  btn.disabled = true;
  btn.textContent = '试听中…';
  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: `你好呀，我是${m.char_name}，听听我的声音感觉怎么样？`,
        voice: m.voice,
        method: m.id,
      }),
    });
    if (!res.ok) throw new Error(res.status);
    const blob = await res.blob();
    await playAudio(blob);
  } catch (e) {
    toast('试听失败：在线音色需要联网，请检查网络', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🔊 试听';
  }
}

/* ---------- 聊天渲染 ---------- */
function scrollToBottom() { els.messageList.scrollTop = els.messageList.scrollHeight; }

function showWelcome() {
  addSystemCard(`👋 我是${charName()}！点击右上角 🕘 的「新的学习」可挑学习方法和伙伴，或直接输入想学的主题开始；也可以先做 🧭 学前测评摸底，定制专属学习路线～`);
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
    av.alt = charName();
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
    <img class="avatar" src="${charAsset('think')}" alt="${charName()}">
    <div class="bubble thinking-bubble"><span class="dots"><i></i><i></i><i></i></span><span class="thinking-text">${charName()}思考中…</span></div>`;
  els.messageList.appendChild(wrap);
  thinkingEl = wrap;
  scrollToBottom();
}
function removeThinking() { if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; } }

/* 等待文案更新（后端 status 事件：制定计划/准备开场等阶段提示） */
function setThinkingText(text) {
  if (!thinkingEl) return;
  const el = thinkingEl.querySelector('.thinking-text');
  if (el && text) el.textContent = text;
}

/* 流式期间禁用输入 */
function setStreamingUI(on) {
  state.streaming = on;
  els.chatInput.disabled = on;
  els.sendBtn.disabled = on;
  els.chatInput.placeholder = on
    ? `${charName()}思考中…`
    : `和${charName()}聊聊你想学什么…（Enter 发送，Shift+Enter 换行）`;
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
/* methodId：学习方法的 id（新建学习时由方法弹窗传入；自动建会话时用上次方法） */
async function createSession(methodId) {
  if (state.streaming) { toast(`请等待${charName()}回复完成`, 'error'); return null; }
  const mid = methodId || lastMethodId();
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method: mid }),
    });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    resetChat();
    state.session = data.session;
    state.phase = (data.session && data.session.status) || 'planning';
    state.points = [];
    state.quizSuggested = new Set(); // 新会话：从头记录已提醒过自测的知识点
    state.materials = [];
    state.messages = [];
    state.currentPointId = null;
    state.progress = 0;
    localStorage.setItem('eduragtutor_method', mid); // 记住本次选择
    await loadMethods();
    applyCharacter(findMethod((data.session && data.session.method) || mid));
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
  if (state.streaming) { toast(`请等待${charName()}回复完成`, 'error'); return; }
  try {
    const res = await fetch(`/api/sessions/${id}`);
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.session = data.session;
    state.phase = (data.session && data.session.status) || 'planning';
    state.points = data.points || [];
    // 恢复历史会话：已掌握的知识点不触发自测建议卡（只对"新完成"的点提醒）
    state.quizSuggested = new Set(
      (data.points || []).filter((p) => p.status === 'mastered').map((p) => p.id)
    );
    state.materials = data.materials || [];
    state.messages = data.messages || [];
    state.currentPointId = null;
    state.progress = (data.session && data.session.progress) || 0;

    // 人物随会话的学习方法切换
    await loadMethods(true);
    applyCharacter(findMethod((data.session && data.session.method) || 'socratic'));

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
  state.quizSuggested = new Set();
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
    toast(`请先配置大模型 API（右上角 ⚙️），${charName()}才能思考哦`, 'error');
    openSettings(true);
    return;
  }
  // 无会话时：这是用户第一次说出想学什么 —— 先给测评建议卡，不直接开课
  if (!state.session) {
    els.chatInput.value = '';
    autoResizeInput();
    showAssessSuggestion(content);
    return;
  }
  els.chatInput.value = '';
  autoResizeInput();
  renderMessage('user', content);
  streamChat(content);
}

/* 首次说出想学什么：渲染测评建议卡（做测评 or 直接开课） */
function showAssessSuggestion(topic) {
  const card = document.createElement('div');
  card.className = 'system-card assess-suggest';

  const p = document.createElement('div');
  p.className = 'suggest-text';
  p.textContent =
    `想学「${topic}」？建议先做一次 🧭 学前测评：约 10 道选择题摸个底，` +
    '再为你定制「先用什么方法学、学到什么程度、再换什么方法巩固」的学习路线～';
  card.appendChild(p);

  const row = document.createElement('div');
  row.className = 'suggest-actions';
  const assessBtn = document.createElement('button');
  assessBtn.className = 'primary-btn';
  assessBtn.type = 'button';
  assessBtn.textContent = '开始测评';
  assessBtn.addEventListener('click', () => openAssessModal(topic));
  const skipBtn = document.createElement('button');
  skipBtn.className = 'mini-btn';
  skipBtn.type = 'button';
  skipBtn.textContent = '跳过，直接开始学习';
  skipBtn.addEventListener('click', async () => {
    assessBtn.disabled = true;
    skipBtn.disabled = true;
    const session = await createSession(lastMethodId());
    if (session) {
      renderMessage('user', topic);
      streamChat(topic);
    } else {
      assessBtn.disabled = false;
      skipBtn.disabled = false;
    }
  });
  row.appendChild(assessBtn);
  row.appendChild(skipBtn);
  card.appendChild(row);

  els.messageList.appendChild(card);
  scrollToBottom();
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
      case 'status':
        setThinkingText(obj.text); // 阶段性等待提示（规划/开场等）
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
    const msg = (e && e.message) ? e.message : String(e);
    toast(`消息发送失败：${msg}`, 'error');
    addSystemCard(`⚠️ 消息发送失败：${msg}（请把这条截图给开发者）`);
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
  if (Array.isArray(ev.points)) {
    state.points = ev.points;
    checkPhaseQuiz(ev.points); // 有知识点新变为"已掌握"→ 插阶段自测建议卡
  }
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
  if (state.streaming) { toast(`请等待${charName()}回复完成`, 'error'); return; }

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

/* ---------- 联网找资料 ---------- */
function openSearchModal() {
  els.searchModal.classList.remove('hidden');
  els.searchInput.focus();
}

function closeSearchModal() {
  els.searchModal.classList.add('hidden');
}

async function performSearch() {
  const q = els.searchInput.value.trim();
  if (!q) { toast('先输入想找的资料关键词', 'error'); return; }
  if (state.searching) return;
  state.searching = true;
  state.searchQuery = q;
  els.searchGoBtn.disabled = true;
  els.searchResults.innerHTML = '<div class="search-empty">🔍 搜索中…</div>';
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&type=${state.searchType}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderSearchResults(data.results || []);
  } catch (e) {
    els.searchResults.innerHTML = '';
    els.searchStatus.textContent = '搜索失败，请稍后再试～';
    toast(`搜索失败：${e.message}`, 'error');
  } finally {
    state.searching = false;
    els.searchGoBtn.disabled = false;
  }
}

function renderSearchResults(list) {
  els.searchResults.innerHTML = '';
  if (!list.length) {
    els.searchStatus.textContent = '没有找到相关资料，换个关键词或类型试试～';
    return;
  }
  els.searchStatus.textContent = `找到 ${list.length} 条结果，文档类可直接下载入库`;
  list.forEach((r) => {
    const item = document.createElement('div');
    item.className = 'search-result';

    const head = document.createElement('div');
    head.className = 'sr-head';
    const title = document.createElement('a');
    title.className = 'sr-title';
    title.textContent = r.title;
    title.title = r.title;
    title.addEventListener('click', (ev) => { ev.preventDefault(); openExternal(r.url); });
    const host = document.createElement('span');
    host.className = 'sr-host';
    host.textContent = r.host;
    head.appendChild(title);
    head.appendChild(host);

    const snip = document.createElement('p');
    snip.className = 'sr-snip';
    snip.textContent = r.snippet || '（无摘要）';

    const actions = document.createElement('div');
    actions.className = 'sr-actions';
    const dlBtn = document.createElement('button');
    dlBtn.className = 'mini-btn';
    dlBtn.type = 'button';
    dlBtn.textContent = '📥 下载入库';
    dlBtn.addEventListener('click', () => downloadFromWeb(r.url, dlBtn));
    const openBtn = document.createElement('button');
    openBtn.className = 'mini-btn';
    openBtn.type = 'button';
    openBtn.textContent = '🔗 浏览器打开';
    openBtn.addEventListener('click', () => openExternal(r.url));
    actions.appendChild(dlBtn);
    actions.appendChild(openBtn);

    item.appendChild(head);
    item.appendChild(snip);
    item.appendChild(actions);
    els.searchResults.appendChild(item);
  });
}

/* 下载到资料库：复用上传成功后的刷新逻辑（列表 + 学习计划） */
async function downloadFromWeb(url, btn) {
  if (!state.session) { toast('请先点击「新的学习」创建会话', 'error'); return; }
  if (state.downloadingUrl) { toast('已有资料在下载中，请稍候', 'error'); return; }
  state.downloadingUrl = url;
  const oldText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '下载中…';
  try {
    const res = await fetch('/api/materials/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, session_id: state.session.id }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.materials.push(data.material);
    renderMaterials();
    if (Array.isArray(data.points)) {
      state.points = data.points;
      renderPoints();
    }
    toast(data.replanned ? '资料已入库，学习计划已更新' : '资料已下载入库', 'success');
  } catch (e) {
    toast(`下载失败：${e.message}`, 'error');
  } finally {
    state.downloadingUrl = null;
    btn.disabled = false;
    btn.textContent = oldText;
  }
}

/* 用系统默认浏览器打开链接 */
async function openExternal(url) {
  try {
    const res = await fetch('/api/open_url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    toast('无法在浏览器中打开该链接', 'error');
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
        // 音色由学伴决定（voice.txt 可覆盖）；method 让后端优先用该学伴的离线语音包
        body: JSON.stringify({
          text,
          voice: (state.method && state.method.voice) || '',
          method: (state.method && state.method.id) || '',
        }),
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
    // pause 也要收尾：stopTts 打断时 pause 不触发 ended，
    // 缺这个会让 await playAudio 永远挂起、ttsBusy 卡死、后续语音全部静默
    audio.onpause = clean;
    audio.play().catch(clean);
  });
}

function stopTts() {
  ttsQueue.length = 0;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
}

/* ---------- 启动 ---------- */
init();
