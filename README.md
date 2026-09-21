# Edu-RAG-Tutor —— AI 学习伙伴 · 六种学习方法

[English](./README_EN.md) | 简体中文

一个运行在 Windows 桌面的 AI 学习伙伴。内置六种经典学习方法——**苏格拉底提问、费曼学习、格物致知、间隔复习、SQ3R 阅读、检索练习**，每位方法对应一位专属 AI 学伴（思小诘 / 费小曼 / 格小致 / 温小习 / 阅小思 / 检小索），为你制定学习计划、逐个知识点教学、评估掌握度、查漏补缺，最后生成学习总结。

## 🎬 演示视频

<!-- 补充演示视频（二选一，替换本区块即可）：
① 推荐：在 github.com 网页上编辑 README.md，把录好的 .mp4 直接拖进编辑框，
   GitHub 会自动上传并生成可在 README 内直接播放的视频链接；
② 外链：上传到 B站 / YouTube，用 [![封面图](封面图地址)](视频地址) 的格式嵌入。
   （建议视频控制在 100MB 内；Windows 可用 Win+G 游戏栏录屏）
-->

📹 演示视频整理中，敬请期待～

计划演示内容：学前测评定制学习路线（或选择学习方法）→ 输入学习主题 → 自动生成学习计划 → 学伴一对一教学 → 阶段奖励与巩固验收 → 语音互动 → 学习总结。

## ✨ 功能特性

- **🧭 六种学习方法 · 六位 AI 学伴**：苏格拉底提问（思小诘）/ 费曼学习（费小曼）/ 格物致知（格小致）/ 间隔复习（温小习）/ SQ3R 阅读（阅小思）/ 检索练习（检小索）；状态机驱动完整学习流程——`规划 → 学习 → 巩固 → 查漏补缺 → 总结`，每轮评估你的回答并动态调整掌握度
- **📋 学前测评 · 定制学习路线**：说出想学的主题，先做约 10 道摸底选择题（由易到难），自动判分评估掌握程度，再由 AI 规划 2~4 个阶段的多方法学习路线——先用什么方法学、学到什么程度、再换什么方法巩固，每个阶段附达标切换标准，可一键按路线开课
- **🎉 阶段奖励与巩固学习**：每个知识点达标后，先给一段正反馈鼓励 + 阶段小结（指出不足），再出一道巩固验收题，答对才真正进入下一阶段
- **📚 本地 RAG 知识库**：上传 `.txt / .md / .pdf / .docx` 学习资料，本地解析分块、向量化（bge-small-zh）入 chromadb，教学时检索作为依据，全程数据不出本机
- **🌐 联网找资料**：内置搜索可直接查找电子版学习资料（支持按 PDF / PPT / Word 筛选），文档类结果一键下载入库并自动向量化，网页类一键浏览器打开
- **🎭 六位专属学伴形象**：每种学习方法对应专属 2D 角色，立绘可点击互动（随机表情 + 专属俏皮话 + 语音朗读，打断式即点即说），待机小动作、说话节奏动画；向对应目录放图即生效（兼容 PNG/JPG/GIF 动图，缺图自动回退）
- **🔊 语音合成**：6 位学伴各有固定专属音色（选择卡片可 🔊 试听），也可放 `voice.txt` 自定义音色、放离线语音包（sherpa-onnx 模型）；合成优先级 `在线音色 → 系统语音 → 离线语音包`，详见 [语音包说明.txt](./static/assets/character/语音包说明.txt)
- **🎤 语音输入**：输入栏左侧 🎤 点击说话，离线识别（sherpa-onnx SenseVoice，纯本地不上传）把文字填进输入框，动口不动手
- **🎯 专注模式**：一键隐藏角色面板，专注对话学习
- **🕘 历史会话**：学习进度本地持久化（SQLite），随时恢复上次学习
- **⚙️ 界面可配置大模型**：支持任意 OpenAI 兼容 API（DeepSeek / 通义千问 / Kimi / 智谱 / 本地 Ollama…），安装版首启向导输入自己的 API Key 即可使用

## 🖥️ 技术栈

| 层 | 技术 |
|---|---|
| 桌面窗口 | pywebview（Edge WebView2） |
| 后端 | Python · FastAPI · uvicorn（单进程） |
| 大模型 | OpenAI 兼容 API（SSE 流式输出） |
| 向量检索 | chromadb · sentence-transformers（BAAI/bge-small-zh-v1.5） |
| 语音 | 朗读：edge-tts（在线）→ pyttsx3（系统兜底）→ sherpa-onnx（离线语音包）· 输入：sherpa-onnx SenseVoice（离线识别） |
| 存储 | SQLite（会话 / 消息 / 知识点 / 测评记录 / 偏好设置） |
| 前端 | 原生 HTML/CSS/JS，无框架无构建 |

## 📁 项目结构

```
├── run.py                 # 启动入口（开发/打包通用）
├── app/
│   ├── main.py            # FastAPI 组装 + pywebview 窗口
│   ├── config.py          # pydantic-settings 配置
│   ├── api/               # 路由：会话/聊天SSE/学前测评/资料上传/联网搜索/设置/TTS
│   ├── tutor/             # 教学引擎：状态机/提示词/LLM客户端
│   ├── kb/                # RAG：解析分块/向量化/检索
│   ├── tts/               # 语音合成（音色/缓存/降级）
│   └── db/                # SQLite DAO
├── static/                # 前端 + 学伴形象资源
│   └── assets/character/  # 形象目录（default + 各学习方法，放图即生效）
├── installer.iss          # Inno Setup 安装包脚本
├── build.bat              # 一键打包（exe + 安装包）
└── requirements.txt
```

## 🚀 快速开始

### 方式一：下载安装包（推荐）

1. **下载安装包**：[EduRAGTutor-Setup-1.1.0.exe](https://github.com/qinjin1021/Edu-RAG-Tutor/releases/download/v1.1.0/EduRAGTutor-Setup-1.1.0.exe)（约 350 MB）
   也可前往 [Releases 页面](https://github.com/qinjin1021/Edu-RAG-Tutor/releases/latest) 查看全部版本
2. **安装**：双击运行，按向导下一步即可（无需管理员权限）
3. **配置**：首次启动会弹出向导，输入你自己的大模型 API Key（推荐 [DeepSeek](https://platform.deepseek.com)：注册后在「API Keys」创建；也支持通义千问 / Kimi / 智谱 / 本地 Ollama 等 OpenAI 兼容服务）
4. **开始学习**：选择一种学习方法与学伴，或先做「学前测评」定制学习路线，输入想学的主题即可开始 🎉

> 💡 安装包已内置本地 embedding 模型，安装后向量检索离线可用；大模型对话与在线语音需联网。学习数据保存在本机 `%APPDATA%\EduRAGTutor\`。

### 方式二：源码运行（开发者）

环境要求：Windows 10+ · Python 3.10+

```bash
# 1. 克隆
git clone https://github.com/qinjin1021/Edu-RAG-Tutor.git
cd Edu-RAG-Tutor

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 3. 配置大模型 API（复制模板后填入你的 Key）
copy .env.example .env
#    编辑 .env：LLM_API_KEY=sk-...（支持 DeepSeek 等 OpenAI 兼容服务）

# 4. 启动
.venv\Scripts\python run.py
```

首次启动会自动下载 embedding 模型（约 100MB，需联网；已配置 hf-mirror 镜像）。
也可以跳过 `.env`，启动后在界面右上角 ⚙️ 设置弹窗中填写 API Key。

## 📦 打包安装程序

依赖 [Inno Setup 6](https://jrsoftware.org/isdl.php)：

```bash
build.bat
```

产物：
- `dist\EduRAGTutor\EduRAGTutor.exe` —— 绿色版，可直接运行
- `installer\EduRAGTutor-Setup-1.0.0.exe` —— 分发用安装包（安装后用户输入自己的 API Key 即可使用）

## ⚙️ 配置项（.env）

| 变量 | 说明 | 默认 |
|---|---|---|
| `LLM_API_KEY` | 大模型 API Key | 无（必填） |
| `LLM_BASE_URL` | OpenAI 兼容接口地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名 | `deepseek-chat` |
| `MASTERY_THRESHOLD` | 知识点掌握达标线（%） | `80` |
| `TTS_VOICE` | edge-tts 音色 | `zh-CN-xiaoyiNeural` |
| `DATA_DIR` | 数据目录 | `data` |

完整项见 [.env.example](./.env.example)。

## 🔒 数据与隐私

- 学习数据（会话/消息/知识点/资料向量/音频缓存）全部存储在**本地**：开发模式在项目 `data/`，打包版在 `%APPDATA%\EduRAGTutor\data\`
- API Key 仅保存在本机数据库，界面上打码显示
- 上传的资料仅用于本地向量检索，不发送到任何第三方（仅发送给**你自己配置的**大模型 API 用于生成回复）

## 🧩 更换学习伙伴形象与声音

六位学伴的形象目录位于 `static/assets/character/`（`default/` 为公共兜底形象，`socratic / feynman / gewu / spaced / sq3r / retrieval` 对应各学习方法）。向对应方法文件夹放入 5 张表情图（文件名固定：`idle / think / happy / encourage / surprise`，支持 `.png/.jpg/.gif/.webp/.apng`），重开"新的学习"选择弹窗即生效，无需改代码；缺图自动回退 `default/` 同名表情。

每位学伴出厂即有固定专属音色（选择卡片可 🔊 试听）；想换声音，在同目录放一个 `voice.txt` 写入音色 ID 即可；想要完全离线的专属声音，可在学伴目录的 `voice/` 子目录放入 sherpa-onnx 离线语音模型，详见 [语音包说明.txt](./static/assets/character/语音包说明.txt)。

## 📝 说明

- 开发过程中遇到的问题与解决方案记录见 [问题总结.txt](./问题总结.txt)
- 本项目仅供学习交流使用

## 📖 English Version

See [README_EN.md](./README_EN.md) for the English documentation.
