# MyOrigins AI Documentary Generator

A full-stack web application that transforms family history data into a cinematic AI-generated documentary — complete with a narrated script, voice audio, and a slideshow video.

Built as a feature for [MyOrigins.ai](https://myorigins.ai) — a platform dedicated to preserving family legacies.

🌐 **Live Demo:** https://myorigins-documentary.vercel.app

---

## Features

- AI-generated documentary script using LLaMA3 (Ollama)
- Text-to-speech voice narration using gTTS
- Automatic slideshow video generation using FFmpeg
- Photo uploads with drag-and-drop support
- Documentary history saved to MySQL database
- React frontend styled to match MyOrigins.ai brand

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React.js |
| Backend | Python / Flask |
| Database | MySQL |
| AI Script | LLaMA3 via Ollama |
| Voice | Google Text-to-Speech (gTTS) |
| Video | FFmpeg |
| Deployment | Vercel (frontend) |

---

## How to Run Locally

### Prerequisites
- Python 3.x
- Node.js
- MySQL
- FFmpeg
- Ollama with LLaMA3

### Backend
```bash
cd "AI Documentary"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

### Frontend
```bash
cd frontend
npm install
npm start
```

---

## Screenshots

> Generate a documentary by entering your family's details, uploading photos, and clicking Generate.

---

## Author

Karan Khullar — built for MyOrigins.ai
