# Socratis · 思小诘 —— 苏格拉底式 AI 学习助手

[English](./README_EN.md) | 简体中文

一个运行在 Windows 桌面的 AI 学习伙伴。她不直接告诉你答案，而是像苏格拉底一样**用问题引导你自己思考**——制定学习计划、逐个知识点提问教学、评估掌握度、查漏补缺，最后生成学习总结。

## 🎬 演示视频

<!-- 补充演示视频（二选一，替换本区块即可）：
① 推荐：在 github.com 网页上编辑 README.md，把录好的 .mp4 直接拖进编辑框，
   GitHub 会自动上传并生成可在 README 内直接播放的视频链接；
② 外链：上传到 B站 / YouTube，用 [![封面图](封面图地址)](视频地址) 的格式嵌入。
   （建议视频控制在 100MB 内；Windows 可用 Win+G 游戏栏录屏）
-->

📹 演示视频整理中，敬请期待～

计划演示内容：输入学习主题 → 自动生成学习计划 → 苏格拉底式问答教学 → 阶段奖励与巩固验收 → 语音互动 → 学习总结。

## ✨ 功能特性

- **🧭 苏格拉底式教学引擎**：状态机驱动完整学习流程——`规划 → 学习 → 巩固 → 查漏补缺 → 总结`，每轮评估你的回答并动态调整掌握度
- **🎉 阶段奖励与巩固学习**：每个知识点达标后，先给一段正反馈鼓励 + 阶段小结（指出不足），再出一道巩固验收题，答对才真正进入下一阶段
- **📚 本地 RAG 知识库**：上传 `.txt / .md / .pdf / .docx` 学习资料，本地解析分块、向量化（bge-small-zh）入 chromadb，教学时检索作为依据，全程数据不出本机
- **🎭 2D 互动角色**：立绘可点击互动（随机表情 + 俏皮话 + 语音朗读），待机小动作、说话节奏动画；支持**多套皮肤**（目录放图即生效，兼容 PNG/GIF 动图）
- **🔊 语音合成与音色切换**：edge-tts 在线优先（6 种中文音色可试听切换），断网自动降级 pyttsx3 系统语音
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
| 语音 | edge-tts（在线）→ pyttsx3（离线兜底） |
| 存储 | SQLite（会话 / 消息 / 知识点 / 偏好设置） |
| 前端 | 原生 HTML/CSS/JS，无框架无构建 |

## 📁 项目结构

```
├── run.py                 # 启动入口（开发/打包通用）
├── app/
│   ├── main.py            # FastAPI 组装 + pywebview 窗口
│   ├── config.py          # pydantic-settings 配置
│   ├── api/               # 路由：会话/聊天SSE/资料上传/设置/TTS
│   ├── tutor/             # 教学引擎：状态机/提示词/LLM客户端
│   ├── kb/                # RAG：解析分块/向量化/检索
│   ├── tts/               # 语音合成（音色/缓存/降级）
│   └── db/                # SQLite DAO
├── static/                # 前端 + 角色皮肤资源
│   └── assets/character/  # 皮肤目录（default/ 等，放图即生效）
├── installer.iss          # Inno Setup 安装包脚本
├── build.bat              # 一键打包（exe + 安装包）
└── requirements.txt
```

## 🚀 快速开始

### 方式一：下载安装包（推荐）

1. **下载安装包**：[SiXiaoJie-Setup-1.0.0.exe](https://github.com/qinjin1021/Socratis/releases/download/v1.0.0/SiXiaoJie-Setup-1.0.0.exe)（约 231 MB）
   也可前往 [Releases 页面](https://github.com/qinjin1021/Socratis/releases/latest) 查看全部版本
2. **安装**：双击运行，按向导下一步即可（无需管理员权限）
3. **配置**：首次启动会弹出向导，输入你自己的大模型 API Key（推荐 [DeepSeek](https://platform.deepseek.com)：注册后在「API Keys」创建；也支持通义千问 / Kimi / 智谱 / 本地 Ollama 等 OpenAI 兼容服务）
4. **开始学习**：输入想学的主题，思小诘会制定计划并开始苏格拉底式提问教学 🎉

> 💡 安装包已内置本地 embedding 模型，安装后向量检索离线可用；大模型对话与在线语音需联网。学习数据保存在本机 `%APPDATA%\SiXiaoJie\`。

### 方式二：源码运行（开发者）

环境要求：Windows 10+ · Python 3.10+

```bash
# 1. 克隆
git clone https://github.com/qinjin1021/Socratis.git
cd Socratis

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
- `dist\SiXiaoJie\SiXiaoJie.exe` —— 绿色版，可直接运行
- `installer\SiXiaoJie-Setup-1.0.0.exe` —— 分发用安装包（安装后用户输入自己的 API Key 即可使用）

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

- 学习数据（会话/消息/知识点/资料向量/音频缓存）全部存储在**本地**：开发模式在项目 `data/`，打包版在 `%APPDATA%\SiXiaoJie\data\`
- API Key 仅保存在本机数据库，界面上打码显示
- 上传的资料仅用于本地向量检索，不发送到任何第三方（仅发送给**你自己配置的**大模型 API 用于生成回复）

## 🧩 添加自定义皮肤

在 `static/assets/character/` 下新建文件夹，放入 5 张表情图（文件名固定：`idle / think / happy / encourage / surprise`，支持 `.png/.gif/.webp`），可选添加 `skin.json`：

```json
{ "name": "我的新皮肤" }
```

重启后设置弹窗的"形象皮肤"下拉框会自动出现新皮肤，无需改代码。

## 📝 说明

- 开发过程中遇到的问题与解决方案记录见 [问题总结.txt](./问题总结.txt)
- 本项目仅供学习交流使用

## 📖 English Version

See [README_EN.md](./README_EN.md) for the English documentation.
