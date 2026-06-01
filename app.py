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

#saves documentaries details into mysql
def save_documentary(family_name, origin, current_location, migration_period, tone, length_seconds, script, audio_url, video_url):
    try:
        db = get_db() #connects to mysql database
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

#cleans script for ai voice generator
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
#folder setup
AUDIO_DIR = os.path.join("static", "audio")
VIDEO_DIR = os.path.join("static", "video")
UPLOAD_DIR = os.path.join("static", "uploads")
PHOTO_DIR = "photos"  # fallback photos if user does not upload any

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
#When the app starts up, it automatically creates 
# the folders needed to store audio files, video files, and uploaded photos
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)



# ---------- Utility helpers ----------

#checks if user uploaded valid file, only jpeg, jpg, png
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

#normalizes all photos before ran in FFmpeg so it can process properly
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

# family tree data exported from the MyOrigins.ai platform. This function 
# opens that file and loads it into Python so the app can read 
# the family member details like names, birthplaces, relationships
def load_family_json(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

#The MyOrigins family tree can contain dozens of relatives, 
# so I wrote a function that identifies the primary subject 
# of the documentary automatically based on the data structure.
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

#I built a lookup table to efficiently access any family member 
# by their ID, rather than searching through the entire dataset every time
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