# Edu-RAG-Tutor — An AI Learning Companion with Six Learning Methods

English | [简体中文](./README.md)

A Windows desktop AI study buddy with six classic learning methods built in — **Socratic questioning, Feynman technique, inquiry-based learning, spaced repetition, SQ3R reading, and retrieval practice**. Each method comes with its own AI companion (Sixiaojie / Feixiaoman / Gexiaozhi / Wenxiaoxi / Yuexiaosi / Jianxiasuo) who builds a study plan, teaches point by point, tracks mastery, fills gaps, and wraps up with a learning summary.

## 🎬 Demo Video

<!-- To add the demo video (choose one, then replace this block):
① Recommended: edit README_EN.md on github.com and drag your .mp4 file directly
   into the editor — GitHub uploads it and generates an inline-playable link;
② External link: upload to YouTube / Bilibili and embed with
   [![thumbnail](thumbnail-url)](video-url) format.
   (Keep the video under ~100MB; on Windows use Win+G Game Bar to record.)
-->

📹 Demo video coming soon~

Planned walkthrough: placement assessment for a customized learning route (or pick a learning method) → enter a topic → auto-generated study plan → one-on-one companion teaching → stage reward & consolidation quiz → voice interaction → learning summary.

## ✨ Features

- **🧭 Six Learning Methods · Six AI Companions** — Socratic questioning (Sixiaojie) / Feynman technique (Feixiaoman) / inquiry-based learning (Gexiaozhi) / spaced repetition (Wenxiaoxi) / SQ3R reading (Yuexiaosi) / retrieval practice (Jianxiasuo); a state machine drives the full learning flow: `Planning → Learning → Consolidation → Review → Summary`, evaluating each of your answers and adjusting mastery dynamically
- **📋 Placement Assessment & Custom Learning Route** — name any topic and take a ~10-question multiple-choice placement quiz (easy → hard); the app grades it automatically, assesses your level, then the LLM plans a 2–4 stage multi-method route — which method to start with, to what depth, and which method to consolidate with — each stage with a clear milestone for switching; start any stage with one click
- **🎉 Stage Rewards & Consolidation** — when a knowledge point reaches the threshold, you get positive encouragement plus a stage recap (including weaknesses), then one consolidation question; pass it to truly move on
- **📚 Local RAG Knowledge Base** — upload `.txt / .md / .pdf / .docx` study materials; they are parsed, chunked and embedded locally (bge-small-zh) into chromadb and retrieved during teaching — your data never leaves your machine
- **🌐 Web Material Search** — search the web for study materials from within the app (filter by PDF / PPT / Word); document results can be downloaded into the knowledge base and auto-embedded, web pages open in your browser with one click
- **🎭 Dedicated Companion Avatars** — each learning method has its own 2D character; click the character for reactions (random emotion + a per-companion playful line spoken aloud, interrupt-style playback), idle wiggle and talking animations; just drop images into the method's folder (PNG/JPG/GIF supported, missing images fall back automatically)
- **🔊 Speech Synthesis** — each companion has a fixed signature voice (previewable on the selection card); you can also drop a `voice.txt` for a custom voice or an offline voice pack (sherpa-onnx model); priority: `online voice → system voice → offline pack`, see [语音包说明.txt](./static/assets/character/语音包说明.txt) (Chinese)
- **🎤 Voice Input** — click 🎤 next to the input box, speak, and click again: offline recognition (sherpa-onnx SenseVoice, fully local — no audio ever leaves your machine) fills the transcript into the input box
- **🎯 Focus Mode** — hide the character panel with one click and concentrate on the conversation
- **🕘 Session History** — learning progress persisted locally (SQLite); resume any previous session anytime
- **⚙️ Configure Your Own LLM** — works with any OpenAI-compatible API (DeepSeek / Qwen / Kimi / Zhipu / local Ollama…); the installer build walks first-run users through entering their own API key

## 🖥️ Tech Stack

| Layer | Technology |
|---|---|
| Desktop window | pywebview (Edge WebView2) |
| Backend | Python · FastAPI · uvicorn (single process) |
| LLM | OpenAI-compatible API (SSE streaming) |
| Vector search | chromadb · sentence-transformers (BAAI/bge-small-zh-v1.5) |
| Speech | TTS: edge-tts (online) → pyttsx3 (system) → sherpa-onnx (offline packs) · ASR: sherpa-onnx SenseVoice (offline) |
| Storage | SQLite (sessions / messages / points / assessments / preferences) |
| Frontend | Vanilla HTML/CSS/JS, no framework, no build step |

## 📁 Project Structure

```
├── run.py                 # Entry point (dev & packaged)
├── app/
│   ├── main.py            # FastAPI assembly + pywebview window
│   ├── config.py          # pydantic-settings configuration
│   ├── api/               # Routes: sessions / chat SSE / placement assessment / uploads / web search / settings / TTS
│   ├── tutor/             # Teaching engine: state machine / prompts / LLM client
│   ├── kb/                # RAG: parsing & chunking / embedding / retrieval
│   ├── tts/               # Speech synthesis (voices / cache / fallback)
│   └── db/                # SQLite DAO
├── static/                # Frontend + companion avatars
│   └── assets/character/  # Avatar folders (default + one per method — drop images to add)
├── installer.iss          # Inno Setup installer script
├── build.bat              # One-click build (exe + installer)
└── requirements.txt
```

## 🚀 Quick Start

### Option 1: Download the Installer (Recommended)

1. **Download**: [EduRAGTutor-Setup-1.1.0.exe](https://github.com/qinjin1021/Edu-RAG-Tutor/releases/download/v1.1.0/EduRAGTutor-Setup-1.1.0.exe) (~350 MB)
   Or browse all versions on the [Releases page](https://github.com/qinjin1021/Edu-RAG-Tutor/releases/latest)
2. **Install**: double-click and follow the wizard (no admin rights required)
3. **Configure**: on first launch, enter your own LLM API key (recommended: [DeepSeek](https://platform.deepseek.com) — register and create a key under "API Keys"; Qwen / Kimi / Zhipu / local Ollama and other OpenAI-compatible services also work)
4. **Start learning**: pick a learning method and its companion — or take the placement assessment first for a custom route — then type any topic you want to learn 🎉

> 💡 The installer bundles the local embedding model, so vector search works offline after installation; LLM chat and online voices require internet. All learning data is stored locally in `%APPDATA%\EduRAGTutor\`.

### Option 2: Run from Source (Developers)

Requirements: Windows 10+ · Python 3.10+

```bash
# 1. Clone
git clone https://github.com/qinjin1021/Edu-RAG-Tutor.git
cd Edu-RAG-Tutor

# 2. Create a venv and install dependencies
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 3. Configure your LLM API (copy the template and fill in your key)
copy .env.example .env
#    Edit .env: LLM_API_KEY=sk-... (any OpenAI-compatible service)

# 4. Run
.venv\Scripts\python run.py
```

The first launch downloads the embedding model (~100MB, network required; an hf-mirror endpoint is preconfigured).
You can also skip `.env` and enter your API key in the ⚙️ settings dialog after launch.

## 📦 Building the Installer

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php):

```bash
build.bat
```

Outputs:
- `dist\EduRAGTutor\EduRAGTutor.exe` — portable build, runs directly
- `installer\EduRAGTutor-Setup-1.1.0.exe` — distributable installer (users enter their own API key on first launch)

## ⚙️ Configuration (.env)

| Variable | Description | Default |
|---|---|---|
| `LLM_API_KEY` | LLM API key | none (required) |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.deepseek.com` |
| `LLM_MODEL` | Model name | `deepseek-chat` |
| `MASTERY_THRESHOLD` | Mastery threshold per point (%) | `80` |
| `TTS_VOICE` | edge-tts voice | `zh-CN-xiaoyiNeural` |
| `DATA_DIR` | Data directory | `data` |

See [.env.example](./.env.example) for the full list.

## 🔒 Data & Privacy

- All learning data (sessions / messages / points / material vectors / audio cache) is stored **locally**: `data/` in dev mode, `%APPDATA%\EduRAGTutor\data\` in the packaged build
- Your API key is kept only in the local database and masked in the UI
- Uploaded materials are used solely for local vector retrieval and are never sent to any third party (content is sent only to **your own configured** LLM API to generate replies)

## 🧩 Companion Avatars & Voices

The avatars live in `static/assets/character/` (`default/` is the shared fallback; `socratic / feynman / gewu / spaced / sq3r / retrieval` map to the learning methods). Drop 5 emotion images into a method's folder (fixed names: `idle / think / happy / encourage / surprise`; `.png/.jpg/.gif/.webp/.apng` supported) and reopen the "new learning" dialog — no code changes needed. Missing images automatically fall back to the same emotion in `default/`.

Each companion ships with a fixed signature voice (previewable on the selection card); drop a `voice.txt` with a voice ID to change it, or place a sherpa-onnx offline voice model in the method folder's `voice/` sub-directory for a fully offline voice — see [语音包说明.txt](./static/assets/character/语音包说明.txt) (Chinese).

## 📝 Notes

- Development issues and their solutions (in Chinese) are documented in [问题总结.txt](./问题总结.txt)
- This project is for learning and educational purposes
