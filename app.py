from flask import Flask, request, render_template_string
from werkzeug.utils import secure_filename
from flask_cors import CORS
import os
import subprocess
import uuid
import glob
import json
from PIL import Image
import requests
from moviepy import ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

ELEVENLABS_API_KEY = "sk_54b44fffc385479a3e6970daa8d3cff4075138a36f3bb407"
ELEVENLABS_VOICE_ID = "XB0fDUnXU5powFXDhCwa"  # "Charlotte" - warm Indian English female

app = Flask(__name__)
CORS(app)

import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Welcome133#",
        database="myorigins"
    )

def save_documentary(family_name, origin, current_location, migration_period, tone, length_seconds, script, audio_url, video_url):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO documentaries 
            (family_name, origin, current_location, migration_period, tone, length_seconds, script, audio_url, video_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (family_name, origin, current_location, migration_period, tone, length_seconds, script, audio_url, video_url))
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f">>> DB ERROR: {e}")

# ---------- Settings ----------
PIPER_DATA_DIR = "voices"
import re

def clean_script_for_tts(script):
    # Remove [stage directions]
    script = re.sub(r'\[.*?\]', '', script)
    # Remove "Narrator:" labels
    script = re.sub(r'Narrator:\s*', '', script)
    # Remove opening/closing quotes
    script = script.replace('"', '').replace('"', '').replace('"', '')
    # Remove lines that are empty after cleaning
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    return ' '.join(lines)
PIPER_VOICE = "en_US-lessac-medium"

AUDIO_DIR = os.path.join("static", "audio")
VIDEO_DIR = os.path.join("static", "video")
UPLOAD_DIR = os.path.join("static", "uploads")
PHOTO_DIR = "photos"  # fallback photos if user does not upload any

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

HTML_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>MyOrigins Documentary Generator</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; max-width: 950px; }
      label { font-weight: 600; }
      input, textarea, select, button { font-size: 14px; padding: 8px; margin-top: 6px; }
      input, textarea, select { width: 100%; max-width: 720px; }
      textarea { resize: vertical; }
      .row { margin-bottom: 14px; }
      .btns { display: flex; gap: 10px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
      button { cursor: pointer; width: fit-content; }
      .card { margin-top: 18px; padding: 14px; border: 1px solid #ddd; border-radius: 10px; background: #fafafa; }
      pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; }
      .small { color: #666; font-size: 13px; margin-top: 6px; }
      .error { color: #b00020; font-weight: 600; }
      video, audio { margin-top: 8px; max-width: 100%; }
    </style>
  </head>
  <body>
    <h1>AI Documentary Generator (Prototype)</h1>
    <p class="small">Script: generated from family JSON. Voice: Piper TTS. Video: FFmpeg slideshow.</p>

    <form method="post" id="docForm" enctype="multipart/form-data">
      <div class="row">
        <label>Family Name</label><br>
        <input type="text" name="family_name" value="{{ family_name }}" required>
      </div>

      <div class="row">
        <label>Origin</label><br>
        <input type="text" name="origin" value="{{ origin }}" required>
      </div>

      <div class="row">
        <label>Current Location</label><br>
        <input type="text" name="current_location" value="{{ current_location }}">
      </div>

      <div class="row">
        <label>Migration Period</label><br>
        <input type="text" name="migration_period" value="{{ migration_period }}">
      </div>

      <div class="row">
        <label>Migration Story / Biography Notes</label><br>
        <textarea name="migration_story" rows="5">{{ migration_story }}</textarea>
      </div>

      <div class="row">
        <label>Traditions (optional)</label><br>
        <input type="text" name="traditions" value="{{ traditions }}" placeholder="Diwali gatherings, family meals...">
      </div>

      <div class="row">
        <label>Core Values (optional)</label><br>
        <input type="text" name="values" value="{{ values }}" placeholder="Hard work, sacrifice, unity...">
      </div>

      <div class="row">
        <label>Tone</label><br>
        <select name="tone">
          <option value="Emotional" {% if tone == "Emotional" %}selected{% endif %}>Emotional</option>
          <option value="Celebratory" {% if tone == "Celebratory" %}selected{% endif %}>Celebratory</option>
          <option value="Inspirational" {% if tone == "Inspirational" %}selected{% endif %}>Inspirational</option>
          <option value="Funny" {% if tone == "Funny" %}selected{% endif %}>Funny</option>
        </select>
      </div>

      <div class="row">
        <label>Length</label><br>
        <select name="length">
          <option value="60" {% if length == "60" %}selected{% endif %}>1 minute</option>
          <option value="120" {% if length == "120" %}selected{% endif %}>2 minutes</option>
          <option value="180" {% if length == "180" %}selected{% endif %}>3 minutes</option>
        </select>
      </div>

      <div class="row">
        <label>
          <input type="checkbox" name="make_voice" value="yes" {% if make_voice %}checked{% endif %}>
          Generate AI voice narration (Piper)
        </label>
      </div>

      <div class="row">
        <label>Upload Photos for Documentary</label><br>
        <input type="file" id="photos" name="photos" multiple accept=".jpg,.jpeg,.png">
        <div class="small">You can upload multiple JPG or PNG images.</div>
        <div id="photoList" class="small" style="margin-top:8px;"></div>
        <div id="photoPreview" style="display:flex; gap:10px; flex-wrap:wrap; margin-top:12px;"></div>
      </div>

      <div class="btns">
        <button type="submit" id="genBtn">Generate Documentary</button>
        {% if script %}
          <button type="button" id="copyBtn">Copy Script</button>
        {% endif %}
      </div>
    </form>

    {% if error %}
      <p class="error">Error: {{ error }}</p>
    {% endif %}

    {% if script %}
      <div class="card">
        <h2>Generated Script</h2>
        <pre id="scriptBox">{{ script }}</pre>

        {% if audio_url %}
          <h3 style="margin-top:16px;">AI Voice Narration</h3>
          <audio controls src="{{ audio_url }}"></audio>
        {% endif %}

        {% if video_url %}
          <h3 style="margin-top:16px;">Documentary Video</h3>
          <video controls width="720" src="{{ video_url }}"></video>
        {% endif %}
      </div>
    {% endif %}

    <script>
  // Loading state
  const form = document.getElementById("docForm");
  form.addEventListener("submit", () => {
    const btn = document.getElementById("genBtn");
    btn.disabled = true;
    btn.innerText = "Generating…";
  });

  // Copy script button
  const copyBtn = document.getElementById("copyBtn");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = document.getElementById("scriptBox").innerText;
      try {
        await navigator.clipboard.writeText(text);
        copyBtn.innerText = "Copied!";
        setTimeout(() => copyBtn.innerText = "Copy Script", 1200);
      } catch (e) {
        alert("Copy failed. You can manually select + copy the text.");
      }
    });
  }

  // Show selected photo names + previews before submit
  const photoInput = document.getElementById("photos");
  const photoList = document.getElementById("photoList");
  const photoPreview = document.getElementById("photoPreview");

  if (photoInput) {
    photoInput.addEventListener("change", () => {
      photoList.innerHTML = "";
      photoPreview.innerHTML = "";

      if (!photoInput.files || photoInput.files.length === 0) {
        photoList.innerHTML = "No photos selected.";
        return;
      }

      const names = Array.from(photoInput.files).map(file => file.name);
      photoList.innerHTML =
        `<strong>${names.length} photo(s) selected:</strong><br>` + names.join("<br>");

      Array.from(photoInput.files).forEach(file => {
        const reader = new FileReader();

        reader.onload = function(e) {
          const wrapper = document.createElement("div");
          wrapper.style.width = "120px";
          wrapper.style.textAlign = "center";
          wrapper.style.fontSize = "12px";

          const img = document.createElement("img");
          img.src = e.target.result;
          img.style.width = "100%";
          img.style.height = "100px";
          img.style.objectFit = "cover";
          img.style.border = "1px solid #ccc";
          img.style.borderRadius = "8px";

          const caption = document.createElement("div");
          caption.style.marginTop = "4px";
          caption.textContent = file.name;

          wrapper.appendChild(img);
          wrapper.appendChild(caption);
          photoPreview.appendChild(wrapper);
        };

        reader.readAsDataURL(file);
      });
    });
  }
    </script>
  </body>
</html>
"""

# ---------- Utility helpers ----------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize_uploaded_images(upload_folder: str) -> str:
    """
    Converts uploaded images into clean JPG files for FFmpeg.
    Returns the folder containing normalized images.
    """
    normalized_dir = os.path.join(upload_folder, "normalized")
    os.makedirs(normalized_dir, exist_ok=True)

    image_files = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        image_files.extend(glob.glob(os.path.join(upload_folder, ext)))

    count = 0
    for img_path in image_files:
        try:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                out_path = os.path.join(normalized_dir, f"image_{count:03d}.jpg")
                img.save(out_path, "JPEG", quality=95)
                count += 1
        except Exception:
            # skip bad images
            pass

    return normalized_dir

def load_family_json(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_main_person(family_data):
    if isinstance(family_data, list):
        for person in family_data:
            if person.get("main") is True:
                return person
        return family_data[0] if family_data else {}

    if isinstance(family_data, dict):
        persons = family_data.get("persons")
        if isinstance(persons, list) and persons:
            for person in persons:
                if person.get("main") is True:
                    return person
            return persons[0]

    return {}

def build_person_lookup(family_data):
    lookup = {}

    if isinstance(family_data, list):
        for person in family_data:
            person_id = person.get("id")
            if person_id:
                lookup[person_id] = person

    elif isinstance(family_data, dict):
        persons = family_data.get("persons", [])
        for person in persons:
            person_id = person.get("id")
            if person_id:
                lookup[person_id] = person

    return lookup

def get_full_name(person):
    if not person:
        return ""
    data = person.get("data", {})
    return f'{data.get("fn", "")} {data.get("ln", "")}'.strip()

def get_related_names(person, lookup):
    rels = person.get("rels", {})

    father_name = ""
    mother_name = ""
    spouse_names = []
    child_names = []

    father_id = rels.get("father")
    mother_id = rels.get("mother")
    spouse_ids = rels.get("spouses", [])
    child_ids = rels.get("children", [])

    if father_id and father_id in lookup:
        father_name = get_full_name(lookup[father_id])

    if mother_id and mother_id in lookup:
        mother_name = get_full_name(lookup[mother_id])

    for spouse_id in spouse_ids:
        if spouse_id in lookup:
            spouse_names.append(get_full_name(lookup[spouse_id]))

    for child_id in child_ids:
        if child_id in lookup:
            child_names.append(get_full_name(lookup[child_id]))

    return father_name, mother_name, spouse_names, child_names

def json_person_to_form_data(person, family_data):
    data = person.get("data", {})
    first_name = data.get("fn", "")
    last_name = data.get("ln", "")
    birthplace = data.get("birthplace", "")
    birthday = data.get("birthday", "")
    living_status = data.get("livingStatus", "")

    full_name = f"{first_name} {last_name}".strip()

    lookup = build_person_lookup(family_data)
    father_name, mother_name, spouse_names, child_names = get_related_names(person, lookup)

    story_parts = []

    if full_name and birthplace:
        sentence = f"{full_name} was born in {birthplace}"
        if birthday:
            sentence += f" on {birthday}"
        sentence += "."
        story_parts.append(sentence)

    if father_name and mother_name:
        story_parts.append(f"He is the son of {father_name} and {mother_name}.")
    elif father_name:
        story_parts.append(f"His father is {father_name}.")
    elif mother_name:
        story_parts.append(f"His mother is {mother_name}.")

    if spouse_names:
        if len(spouse_names) == 1:
            story_parts.append(f"He later married {spouse_names[0]}.")
        else:
            story_parts.append(f"He had relationships with {', '.join(spouse_names)}.")

    if child_names:
        if len(child_names) == 1:
            story_parts.append(f"They have one child, {child_names[0]}.")
        else:
            story_parts.append(f"They have {len(child_names)} children: {', '.join(child_names)}.")

    if living_status:
        story_parts.append(f"Current status: {living_status}.")

    biography = " ".join(story_parts)

    return {
        "family_name": last_name,
        "origin": birthplace,
        "current_location": "",
        "migration_period": "",
        "migration_story": biography,
        "traditions": "",
        "values": "",
        "tone": "Emotional",
        "length": "120",
        "make_voice": False
    }

def generate_family_script(main_person, family_json):
    people = build_person_lookup(family_json)

    data = main_person.get("data", {})
    rels = main_person.get("rels", {})

    full_name = f'{data.get("fn", "")} {data.get("ln", "")}'.strip()
    birthday = data.get("birthday")
    birthplace = data.get("birthplace")

    lines = []

    birth = f"{full_name} was born"
    if birthplace:
        birth += f" in {birthplace}"
    if birthday:
        birth += f" on {birthday}"
    birth += "."
    lines.append(birth)

    father_id = rels.get("father")
    mother_id = rels.get("mother")

    father_name = get_full_name(people.get(father_id)) if father_id in people else ""
    mother_name = get_full_name(people.get(mother_id)) if mother_id in people else ""

    if father_name and mother_name:
        lines.append(f"He is the son of {father_name} and {mother_name}.")
    elif father_name:
        lines.append(f"His father is {father_name}.")
    elif mother_name:
        lines.append(f"His mother is {mother_name}.")

    spouses = rels.get("spouses", [])
    if spouses:
        spouse_name = get_full_name(people.get(spouses[0]))
        if spouse_name:
            lines.append(f"He later married {spouse_name}.")

    children = rels.get("children", [])
    if children:
        child_names = []
        for cid in children:
            child_name = get_full_name(people.get(cid))
            if child_name:
                child_names.append(child_name)

        if child_names:
            if len(child_names) == 1:
                lines.append(f"They have one child: {child_names[0]}.")
            else:
                lines.append("Together they have children: " + ", ".join(child_names) + ".")

    return "\n\n".join(lines)

def piper_tts_to_wav(text: str) -> str:
    from gtts import gTTS
    file_id = str(uuid.uuid4())
    mp3_path = os.path.join(AUDIO_DIR, f"{file_id}.mp3")
    tts = gTTS(text=text, lang='en')
    tts.save(mp3_path)
    return f"/static/audio/{file_id}.mp3"

def make_slideshow_video(audio_file_url: str, photo_dir: str, title_text: str = "Family Documentary") -> str:
    import tempfile, shutil

    audio_path = audio_file_url.lstrip("/")
    file_id    = str(uuid.uuid4())
    out_path   = os.path.join(VIDEO_DIR, f"{file_id}.mp4")
    work_dir   = tempfile.mkdtemp()

    try:
        # collect images
        image_files = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            image_files.extend(sorted(glob.glob(os.path.join(photo_dir, ext))))
        if not image_files:
            raise RuntimeError("No valid image files found.")

        # get audio duration
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, check=True
        )
        audio_dur = float(probe.stdout.strip())
        spi       = max(4.0, audio_dur / len(image_files))
        fade_dur  = 0.8
        title_dur = 3.0
        end_dur   = 2.0
        W, H      = 1280, 720

        clip_paths = []

        # --- 1. Title card using PIL (no ffmpeg drawtext) ---
        from PIL import Image as PILImage, ImageDraw, ImageFont
        import numpy as np

        def make_text_card(text, duration, color=(13,13,13), text_color=(255,255,255)):
            card_path = os.path.join(work_dir, f"card_{uuid.uuid4().hex}.mp4")
            # create image with PIL
            img = PILImage.new("RGB", (W, H), color=color)
            draw = ImageDraw.Draw(img)
            # try to load a font, fall back to default
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
            except:
                font = ImageFont.load_default()
            # center text
            bbox = draw.textbbox((0,0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (W - tw) // 2
            y = (H - th) // 2
            draw.text((x, y), text, font=font, fill=text_color)
            img_path = os.path.join(work_dir, f"card_{uuid.uuid4().hex}.jpg")
            img.save(img_path, "JPEG", quality=95)

            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-t", str(duration),
                "-vf", f"fade=t=in:st=0:d={fade_dur},fade=t=out:st={duration-fade_dur}:d={fade_dur}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", card_path
            ], check=True, capture_output=True)
            return card_path

        clip_paths.append(make_text_card(title_text, title_dur))

        # --- 2. Photo clips — smooth zoom NO shake ---
        for i, img_path in enumerate(image_files):
            out_clip = os.path.join(work_dir, f"clip_{i:03d}.mp4")

            # simple smooth scale zoom using scale filter (no zoompan = no shake)
            zoom_in  = i % 2 == 0
            # start scale and end scale
            if zoom_in:
                scale_vf = (
                    f"scale=8000:-1,"
                    f"crop={W}:{H}:"
                    f"x='(iw-{W})/2':"
                    f"y='(ih-{H})/2'"
                )
            else:
                scale_vf = (
                    f"scale=8000:-1,"
                    f"crop={W}:{H}:"
                    f"x='(iw-{W})/2':"
                    f"y='(ih-{H})/2'"
                )

            vf = (
                f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},"
                # letterbox bars
                f"drawbox=x=0:y=0:w={W}:h=40:color=black:t=fill,"
                f"drawbox=x=0:y={H-40}:w={W}:h=40:color=black:t=fill,"
                # vignette
                f"vignette=PI/5,"
                # fades
                f"fade=t=in:st=0:d={fade_dur},"
                f"fade=t=out:st={spi-fade_dur}:d={fade_dur}"
            )

            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", img_path,
                "-t", str(spi),
                "-vf", vf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-r", "24", out_clip
            ], check=True, capture_output=True)
            clip_paths.append(out_clip)

        # --- 3. Ending card ---
        clip_paths.append(make_text_card(
            "A MyOrigins Documentary",
            end_dur,
            color=(13,13,13),
            text_color=(201,168,76)   # gold
        ))

        # --- 4. Concat ---
        concat_list = os.path.join(work_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        silent_video = os.path.join(work_dir, "silent.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", silent_video
        ], check=True, capture_output=True)

        # --- 5. Add audio ---
        subprocess.run([
            "ffmpeg", "-y",
            "-i", silent_video,
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-shortest", out_path
        ], check=True, capture_output=True)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return f"/static/video/{file_id}.mp4"
# ---------- Main route ----------
@app.route("/api/generate", methods=["POST"])
def api_generate():
    from flask import jsonify

    script = None
    audio_url = None
    video_url = None
    error = None

    form_data = {
        "family_name": "",
        "origin": "",
        "current_location": "",
        "migration_period": "",
        "migration_story": "",
        "traditions": "",
        "values": "",
        "tone": "Emotional",
        "length": "120",
        "make_voice": False
    }

    family_json = None
    main_person = None

    json_files = sorted(glob.glob("jsons/*.json"))
    if json_files:
        family_json = load_family_json(json_files[0])
        main_person = extract_main_person(family_json)
        if main_person:
            json_defaults = json_person_to_form_data(main_person, family_json)
            form_data.update(json_defaults)

    for key in list(form_data.keys()):
        if key == "make_voice":
            form_data["make_voice"] = (request.form.get("make_voice") == "yes")
        else:
            form_data[key] = request.form.get(key, "").strip()

    upload_folder = None
    uploaded_files = request.files.getlist("photos")

    if uploaded_files:
        upload_id = str(uuid.uuid4())
        upload_folder = os.path.join(UPLOAD_DIR, upload_id)
        os.makedirs(upload_folder, exist_ok=True)
        saved_count = 0
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(upload_folder, filename))
                saved_count += 1
        if saved_count == 0:
            upload_folder = None
        if saved_count > 0:
            upload_folder = normalize_uploaded_images(upload_folder)

    try:
        if not main_person or not family_json:
            raise RuntimeError("No family JSON data could be loaded.")

        raw_script = generate_family_script(main_person, family_json)
        tone = form_data.get("tone", "Emotional")
        target_words = {"60": 120, "120": 250, "180": 380}.get(form_data.get("length", "120"), 250)

        rewrite_prompt = f"""You are a documentary voiceover narrator.

STRICT RULES:
- Output ONLY the spoken narration words. Nothing else.
- NO stage directions like [music plays] or [cut to]
- NO labels like "Narrator:" or "Scene 1:"
- NO brackets, parentheses, or quotes of any kind
- Just pure continuous spoken narration text

Tone: {tone}
Target: {target_words} words

Biography:
{raw_script}
"""

        r = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3:latest", "prompt": rewrite_prompt, "stream": False, "temperature": 0.5},
            timeout=180
        )
        r.raise_for_status()
        script = r.json().get("response", "").strip()

        if not script:
            raise RuntimeError("Generated script was empty.")

        if form_data["make_voice"]:
            clean = clean_script_for_tts(script)
            audio_url = piper_tts_to_wav(clean)

        if audio_url:
            try:
                photo_dir = upload_folder if upload_folder else PHOTO_DIR
                video_url = make_slideshow_video(
                    audio_url, photo_dir,
                    title_text=f"{form_data['family_name']} Family Documentary"
                )
            except Exception as e:
                print(f">>> VIDEO ERROR: {type(e).__name__}: {e}")

    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    if error:
        return jsonify({"error": error}), 500

    save_documentary(
    form_data.get("family_name", ""),
    form_data.get("origin", ""),
    form_data.get("current_location", ""),
    form_data.get("migration_period", ""),
    form_data.get("tone", ""),
    int(form_data.get("length", 120)),
    script,
    audio_url or "",
    video_url or ""
)

    return jsonify({
    "script": script,
    "audio_url": audio_url,
    "video_url": video_url,
    })

@app.route("/api/history", methods=["GET"])
def api_history():
    from flask import jsonify
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM documentaries ORDER BY created_at DESC LIMIT 20")
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        for row in rows:
            if row.get("created_at"):
                row["created_at"] = str(row["created_at"])
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/", methods=["GET", "POST"])
def home():
    script = None
    audio_url = None
    video_url = None
    error = None

    form_data = {
        "family_name": "",
        "origin": "",
        "current_location": "",
        "migration_period": "",
        "migration_story": "",
        "traditions": "",
        "values": "",
        "tone": "Emotional",
        "length": "120",
        "make_voice": False
    }

    family_json = None
    main_person = None

    

    if request.method == "POST":
        json_files = sorted(glob.glob("jsons/*.json"))
        if json_files:
            family_json = load_family_json(json_files[0])
            main_person = extract_main_person(family_json)
            if main_person:
                json_defaults = json_person_to_form_data(main_person, family_json)
                form_data.update(json_defaults)

        for key in list(form_data.keys()):
            if key == "make_voice":
                form_data["make_voice"] = (request.form.get("make_voice") == "yes")
            else:
                form_data[key] = request.form.get(key, "").strip()

        upload_folder = None
        uploaded_files = request.files.getlist("photos")

        if uploaded_files:
            upload_id = str(uuid.uuid4())
            upload_folder = os.path.join(UPLOAD_DIR, upload_id)
            os.makedirs(upload_folder, exist_ok=True)

            saved_count = 0
            for file in uploaded_files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(upload_folder, filename))
                    saved_count += 1

            if saved_count == 0:
                upload_folder = None
            if saved_count > 0:
                upload_folder = normalize_uploaded_images(upload_folder)

        try:
            if not main_person or not family_json:
                raise RuntimeError("No family JSON data could be loaded.")

            raw_script = generate_family_script(main_person, family_json)

            tone = form_data.get("tone", "Emotional")
            target_words = {"60": 120, "120": 250, "180": 380}.get(form_data.get("length", "120"), 250)

            rewrite_prompt = f"""You are a documentary voiceover narrator.

                STRICT RULES - VIOLATIONS WILL BREAK THE SYSTEM:
                - Output ONLY the spoken narration words. Nothing else.
                - NO stage directions like [music plays] or [cut to]
                - NO labels like "Narrator:" or "Scene 1:"
                - NO brackets, parentheses, or quotes of any kind
                - NO opening or closing music notes
                - Just pure continuous spoken narration text

                Tone: {tone}
                Target: {target_words} words

                Biography:
                {raw_script}
                """

            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3:latest",
                    "prompt": rewrite_prompt,
                    "stream": False,
                    "temperature": 0.5
                },
                timeout=180
            )
            r.raise_for_status()
            script = r.json().get("response", "").strip()

            if not script:
                raise RuntimeError("Generated script was empty.")

            if form_data["make_voice"]:         
                clean = clean_script_for_tts(script) 
                audio_url = piper_tts_to_wav(clean)    

            if audio_url:
                print(">>> Audio URL:", audio_url)
                print(">>> Starting video generation...")
                try:
                    if upload_folder:
                        video_url = make_slideshow_video(audio_url, upload_folder, title_text=f"{form_data['family_name']} Family Documentary")
                    else:
                        video_url = make_slideshow_video(audio_url, PHOTO_DIR, title_text=f"{form_data['family_name']} Family Documentary")
                    print(">>> Video URL:", video_url)
                except Exception as e:
                    print(f">>> VIDEO ERROR: {type(e).__name__}: {e}")

        except subprocess.CalledProcessError as e:
            error = f"Subprocess failed: {e}"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

    return render_template_string(
        HTML_TEMPLATE,
        script=script,
        audio_url=audio_url,
        video_url=video_url,
        error=error,
        **form_data
    )

if __name__ == "__main__":
    print("Starting Flask... open http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)