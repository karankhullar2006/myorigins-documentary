import requests

family_name = "Khullar"
origin = "Punjab, India"
current_city = "Toronto"
migration_year = "1970s"
memories = "Diwali gatherings, strong work ethic, sacrifice for children"

prompt = f"""
You are a professional documentary narrator.

Write a cinematic, emotionally powerful 2-minute narration.

Family Name: {family_name}
Origin: {origin}
Current Location: {current_city}
Migration Period: {migration_year}
Core Memories & Themes: {memories}

IMPORTANT RULES:
- Output narration ONLY.
- Do NOT include stage directions.
- Do NOT include music cues.
- Do NOT include notes.
- Do NOT include commentary.
- Do NOT use parentheses.
- Do NOT label scenes.
- Do NOT explain anything.

Write as a continuous voiceover script.
Deeply emotional, poetic, and grounded.
"""


response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3",
        "prompt": prompt,
        "temperature": 0.8,
        "stream": False
    }
)

data = response.json()
print("\n--- GENERATED SCRIPT ---\n")
print(data["response"])



