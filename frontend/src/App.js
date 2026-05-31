import { useState, useRef } from "react";
import "./App.css";

function Navbar({ page, setPage }) {
  return (
    <nav className="navbar">
      <div className="nav-logo">
        <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="15" fill="#e8f4e0" stroke="#3a7d2c" strokeWidth="1.5" />
          <path d="M16 5 C16 5 9 10 9 16.5 C9 20.4 12.1 23.5 16 23.5 C19.9 23.5 23 20.4 23 16.5 C23 10 16 5 16 5Z" fill="#3a7d2c" opacity="0.25" />
          <circle cx="16" cy="16.5" r="3.5" fill="#3a7d2c" />
          <line x1="16" y1="5" x2="16" y2="13" stroke="#3a7d2c" strokeWidth="1.8" strokeLinecap="round" />
          <line x1="16" y1="20" x2="16" y2="25" stroke="#3a7d2c" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        </svg>
        <span>MyOrigins</span>
      </div>
      <div className="nav-links">
        <a href="https://myorigins.ai">Home</a>
        <a href="https://myorigins.ai/about">About Us</a>
        <a href="https://myorigins.ai/features">Features</a>
        <a href="https://myorigins.ai/blog">Blog</a>
        <span className={page === "generate" ? "active" : ""} onClick={() => setPage("generate")} style={{cursor:"pointer"}}>Generate</span>
        <span className={page === "history" ? "active" : ""} onClick={() => setPage("history")} style={{cursor:"pointer"}}>History</span>
      </div>
      <a href="https://myorigins.ai/get-started" className="btn-nav">Get Started</a>
    </nav>
  );
}

function Hero({ onScrollToForm }) {
  const colors = ["#b8d4a0","#d4c4a0","#a0b8d4","#d4a0b8","#a0d4c4","#d4d4a0","#c4a0d4","#a0c4a0","#d4b8a0"];
  return (
    <section className="hero">
      <div className="hero-text">
        <h1>Create Your<br />Family Documentary</h1>
        <p>Turn your family's history into a cinematic documentary — with AI narration, your photos, and a story worth sharing for generations.</p>
        <button className="btn-green" onClick={onScrollToForm}>Generate Your Documentary</button>
        <p className="hero-badge">No jargon. No hassle. Just your story, beautifully told.</p>
      </div>
      <div className="hero-mosaic">
        {colors.map((bg, i) => <div key={i} className="mosaic-cell" style={{ background: bg }} />)}
      </div>
    </section>
  );
}

function UploadZone({ onFiles, previews }) {
  const inputRef = useRef();
  const [dragging, setDragging] = useState(false);
  return (
    <div className="form-group full">
      <label className="field-label">Upload Photos</label>
      <div
        className={`upload-zone${dragging ? " drag-over" : ""}`}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); onFiles(e.dataTransfer.files); }}
      >
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
        </svg>
        <p>Click or drag photos here</p>
        <span>JPG or PNG supported</span>
        <input ref={inputRef} type="file" name="photos" multiple accept=".jpg,.jpeg,.png" style={{display:"none"}} onChange={(e) => onFiles(e.target.files)} />
      </div>
      {previews.length > 0 && (
        <div className="photo-previews">
          {previews.map((src, i) => <img key={i} src={src} alt="" className="preview-thumb" />)}
        </div>
      )}
    </div>
  );
}

function ResultPanel({ script, audioUrl, videoUrl, onCopy, copied }) {
  return (
    <section className="results-section">
      <div className="result-card">
        <div className="result-header">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6abf5e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>
          </svg>
          <h3>Your Documentary is Ready</h3>
        </div>
        {script && (
          <div className="script-section">
            <div className="script-label-row">
              <span className="section-label">Generated Script</span>
              <button className="copy-btn" onClick={onCopy}>{copied ? "✓ Copied!" : "Copy Script"}</button>
            </div>
            <div className="script-box">{script}</div>
          </div>
        )}
        <div className="media-grid">
          {audioUrl && (
            <div className="media-block">
              <span className="section-label">AI Voice Narration</span>
              <audio controls src={`http://127.0.0.1:5001${audioUrl}`} />
            </div>
          )}
          {videoUrl && (
            <div className="media-block">
              <span className="section-label">Documentary Video</span>
              <video controls src={`http://127.0.0.1:5001${videoUrl}`} />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function HistoryPage() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(null);

  useState(() => {
    fetch("http://127.0.0.1:5001/api/history")
      .then(res => res.json())
      .then(data => { setRecords(data); setLoading(false); })
      .catch(() => { setError("Could not load history."); setLoading(false); });
  }, []);

  return (
    <section className="form-section">
      <div className="form-section-header">
        <h2>Documentary History</h2>
        <p>All previously generated family documentaries.</p>
      </div>
      {loading && <p style={{color:"#a8c898", textAlign:"center"}}>Loading...</p>}
      {error && <div className="error-box">{error}</div>}
      {!loading && records.length === 0 && (
        <p style={{color:"#a8c898", textAlign:"center"}}>No documentaries generated yet.</p>
      )}
      <div className="history-list">
        {records.map((rec) => (
          <div key={rec.id} className="history-card">
            <div className="history-header" onClick={() => setExpanded(expanded === rec.id ? null : rec.id)}>
              <div className="history-meta">
                <span className="history-family">{rec.family_name} Family</span>
                <span className="history-origin">{rec.origin}</span>
                <span className="history-tone">{rec.tone}</span>
              </div>
              <div className="history-right">
                <span className="history-date">{rec.created_at?.slice(0, 10)}</span>
                <span className="history-chevron">{expanded === rec.id ? "▲" : "▼"}</span>
              </div>
            </div>
            {expanded === rec.id && (
              <div className="history-body">
                <div className="script-label-row">
                  <span className="section-label">Script</span>
                </div>
                <div className="script-box">{rec.script}</div>
                <div className="media-grid" style={{marginTop:"16px"}}>
                  {rec.audio_url && (
                    <div className="media-block">
                      <span className="section-label">Audio</span>
                      <audio controls src={`http://127.0.0.1:5001${rec.audio_url}`} />
                    </div>
                  )}
                  {rec.video_url && (
                    <div className="media-block">
                      <span className="section-label">Video</span>
                      <video controls src={`http://127.0.0.1:5001${rec.video_url}`} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function App() {
  const [page, setPage] = useState("generate");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [previews, setPreviews] = useState([]);
  const [copied, setCopied] = useState(false);
  const [photoFiles, setPhotoFiles] = useState([]);

  const handleFiles = (files) => {
    const arr = Array.from(files);
    setPhotoFiles(arr);
    Promise.all(arr.map(f => new Promise(res => { const r = new FileReader(); r.onload = e => res(e.target.result); r.readAsDataURL(f); }))).then(setPreviews);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); setError(""); setResult(null);
    const fd = new FormData(e.target);
    photoFiles.forEach(f => fd.append("photos", f));
    try {
      const res = await fetch("http://127.0.0.1:5001/api/generate", { method: "POST", body: fd });
      const data = await res.json();
      if (data.error) { setError(data.error); }
      else { setResult(data); setTimeout(() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }), 100); }
    } catch {
      setError("Could not connect to Flask. Make sure it's running on port 5001.");
    } finally { setLoading(false); }
  };

  return (
    <div className="app">
      <Navbar page={page} setPage={setPage} />
      {page === "generate" && (
        <>
          <Hero onScrollToForm={() => document.getElementById("gen-form")?.scrollIntoView({ behavior: "smooth" })} />
          <section className="form-section" id="gen-form">
            <div className="form-section-header">
              <h2>Generate Your Documentary</h2>
              <p>Fill in your family's details and let AI bring your story to life.</p>
            </div>
            {error && <div className="error-box">{error}</div>}
            <form onSubmit={handleSubmit} className="doc-form">
              <div className="form-grid">
                <div className="form-group"><label className="field-label">Family Name</label><input type="text" name="family_name" placeholder="e.g. Khullar" required /></div>
                <div className="form-group"><label className="field-label">Origin</label><input type="text" name="origin" placeholder="e.g. Punjab, India" required /></div>
                <div className="form-group"><label className="field-label">Current Location</label><input type="text" name="current_location" placeholder="e.g. Toronto, Canada" /></div>
                <div className="form-group"><label className="field-label">Migration Period</label><input type="text" name="migration_period" placeholder="e.g. 1990s" /></div>
                <div className="form-group full"><label className="field-label">Migration Story / Biography Notes</label><textarea name="migration_story" rows={4} placeholder="Share your family's journey..." /></div>
                <div className="form-group"><label className="field-label">Traditions (optional)</label><input type="text" name="traditions" placeholder="Diwali gatherings, family meals..." /></div>
                <div className="form-group"><label className="field-label">Core Values (optional)</label><input type="text" name="values" placeholder="Hard work, sacrifice, unity..." /></div>
                <div className="form-group">
                  <label className="field-label">Tone</label>
                  <select name="tone"><option value="Emotional">Emotional</option><option value="Celebratory">Celebratory</option><option value="Inspirational">Inspirational</option><option value="Funny">Funny</option></select>
                </div>
                <div className="form-group">
                  <label className="field-label">Length</label>
                  <select name="length"><option value="60">1 minute</option><option value="120">2 minutes</option><option value="180">3 minutes</option></select>
                </div>
                <div className="form-group full">
                  <label className="check-label"><input type="checkbox" name="make_voice" value="yes" /><span>Generate AI voice narration</span></label>
                </div>
                <UploadZone onFiles={handleFiles} previews={previews} />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn-generate" disabled={loading}>
                  {loading ? <><span className="spinner" /> Generating your documentary…</> : "✦ Generate Documentary"}
                </button>
              </div>
            </form>
          </section>
          {result && (
            <div id="results">
              <ResultPanel script={result.script} audioUrl={result.audio_url} videoUrl={result.video_url}
                onCopy={() => { navigator.clipboard.writeText(result.script || ""); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                copied={copied} />
            </div>
          )}
        </>
      )}
      {page === "history" && <HistoryPage />}
      <footer className="footer"><p>© 2026 MyOrigins.ai — Preserve Your Family Legacy</p></footer>
    </div>
  );
}