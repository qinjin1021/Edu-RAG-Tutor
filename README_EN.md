# Socratis — A Socratic AI Learning Companion

English | [简体中文](./README.md)

A Windows desktop AI study buddy. Instead of handing you answers, she guides you to think for yourself the Socratic way — building a study plan, teaching point by point with questions, tracking mastery, filling gaps, and wrapping up with a learning summary.

## 🎬 Demo Video

<!-- To add the demo video (choose one, then replace this block):
① Recommended: edit README_EN.md on github.com and drag your .mp4 file directly
   into the editor — GitHub uploads it and generates an inline-playable link;
② External link: upload to YouTube / Bilibili and embed with
   [![thumbnail](thumbnail-url)](video-url) format.
   (Keep the video under ~100MB; on Windows use Win+G Game Bar to record.)
-->

📹 Demo video coming soon~

Planned walkthrough: enter a topic → auto-generated study plan → Socratic Q&A teaching → stage reward & consolidation quiz → voice interaction → learning summary.

## ✨ Features

- **🧭 Socratic Teaching Engine** — a state machine drives the full learning flow: `Planning → Learning → Consolidation → Review → Summary`, evaluating each of your answers and adjusting mastery dynamically
- **🎉 Stage Rewards & Consolidation** — when a knowledge point reaches the threshold, you get positive encouragement plus a stage recap (including weaknesses), then one consolidation question; pass it to truly move on
- **📚 Local RAG Knowledge Base** — upload `.txt / .md / .pdf / .docx` study materials; they are parsed, chunked and embedded locally (bge-small-zh) into chromadb and retrieved during teaching — your data never leaves your machine
- **🎭 Interactive 2D Character** — click the character for reactions (random emotion + a playful line + spoken aloud), idle wiggle and talking animations; **multiple skins** (just drop images into a folder, PNG/GIF supported)
- **🔊 TTS with Voice Switching** — edge-tts online first (6 Chinese voices, previewable and switchable), automatic fallback to local pyttsx3 when offline
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
| Speech | edge-tts (online) → pyttsx3 (offline fallback) |
| Storage | SQLite (sessions / messages / points / preferences) |
| Frontend | Vanilla HTML/CSS/JS, no framework, no build step |

## 📁 Project Structure

```
├── run.py                 # Entry point (dev & packaged)
├── app/
│   ├── main.py            # FastAPI assembly + pywebview window
│   ├── config.py          # pydantic-settings configuration
│   ├── api/               # Routes: sessions / chat SSE / uploads / settings / TTS
│   ├── tutor/             # Teaching engine: state machine / prompts / LLM client
│   ├── kb/                # RAG: parsing & chunking / embedding / retrieval
│   ├── tts/               # Speech synthesis (voices / cache / fallback)
│   └── db/                # SQLite DAO
├── static/                # Frontend + character skins
│   └── assets/character/  # Skin folders (default/, etc. — drop images to add)
├── installer.iss          # Inno Setup installer script
├── build.bat              # One-click build (exe + installer)
└── requirements.txt
```

## 🚀 Quick Start (Development)

Requirements: Windows 10+ · Python 3.10+

```bash
# 1. Clone
git clone https://github.com/qinjin1021/Socratis.git
cd Socratis

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
- `dist\SiXiaoJie\SiXiaoJie.exe` — portable build, runs directly
- `installer\SiXiaoJie-Setup-1.0.0.exe` — distributable installer (users enter their own API key on first launch)

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

- All learning data (sessions / messages / points / material vectors / audio cache) is stored **locally**: `data/` in dev mode, `%APPDATA%\SiXiaoJie\data\` in the packaged build
- Your API key is kept only in the local database and masked in the UI
- Uploaded materials are used solely for local vector retrieval and are never sent to any third party (content is sent only to **your own configured** LLM API to generate replies)

## 🧩 Adding Custom Skins

Create a new folder under `static/assets/character/` and drop in 5 emotion images (fixed names: `idle / think / happy / encourage / surprise`; `.png/.gif/.webp` supported). Optionally add a `skin.json`:

```json
{ "name": "My New Skin" }
```

After a restart the new skin appears automatically in the settings dropdown — no code changes needed.

## 📝 Notes

- Development issues and their solutions (in Chinese) are documented in [问题总结.txt](./问题总结.txt)
- This project is for learning and educational purposes
