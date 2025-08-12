
import json

def get_language_code(language_name: str) -> str | None:
    lang_file="language.json"
    with open(lang_file, "r", encoding="utf-8") as f:
        languages = json.load(f)
    for lang in languages:
        if lang["name"].lower() == language_name.lower():
            return lang["code"]
    return None