from flask import Flask, render_template, request, redirect, url_for, send_file
import random
from gtts import gTTS
import os
import tempfile
import io
import time
import requests

# ============================================================
# JSONBIN CONFIGURATION
# ============================================================

JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")

if not JSONBIN_BIN_ID or not JSONBIN_API_KEY:
    raise RuntimeError("JSONBIN env vars not set")

JSONBIN_GET_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
JSONBIN_PUT_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# In-memory cache (lifetime = process)
MISSED_WORDS_CACHE = None

# ============================================================
# FLASK APP
# ============================================================

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# ============================================================
# MISSED WORD STORAGE (JSONBIN + CACHE)
# ============================================================

def load_missed_words():
    global MISSED_WORDS_CACHE

    if MISSED_WORDS_CACHE is not None:
        return MISSED_WORDS_CACHE

    try:
        r = requests.get(
            JSONBIN_GET_URL,
            headers={"X-Master-Key": JSONBIN_API_KEY},
            timeout=5
        )
        if r.status_code == 200:
            MISSED_WORDS_CACHE = r.json()["record"].get("missed_words", [])
            return MISSED_WORDS_CACHE
    except Exception as e:
        print("[JSONBIN LOAD ERROR]", e)

    MISSED_WORDS_CACHE = []
    return MISSED_WORDS_CACHE


def save_missed_words():
    global MISSED_WORDS_CACHE

    try:
        r = requests.put(
            JSONBIN_PUT_URL,
            headers={
                "X-Master-Key": JSONBIN_API_KEY,
                "Content-Type": "application/json",
                "X-Bin-Versioning": "false"
            },
            json={"missed_words": MISSED_WORDS_CACHE},
            timeout=5
        )
        return r.status_code == 200
    except Exception as e:
        print("[JSONBIN SAVE ERROR]", e)
        return False


def add_missed_word(word):
    missed_words = load_missed_words()

    for w in missed_words:
        if w["word"] == word:
            w["attempts"] += 1
            save_missed_words()
            return

    missed_words.append({
        "word": word,
        "attempts": 1,
        "correct": 0
    })
    save_missed_words()


def get_missed_words_dict():
    return {w["word"]: w["attempts"] for w in load_missed_words()}

# ============================================================
# WEIGHTED WORD SELECTION
# ============================================================

def rng_word_ids_with_weighting(word_list, start_index, end_index, num_words):
    missed_words = get_missed_words_dict()
    weighted_ids = []

    for word_id in range(start_index, end_index + 1):
        if word_id <= len(word_list):
            word = word_list[word_id - 1].split("(")[0].strip()

            if word in missed_words:
                attempts = missed_words[word]
                weight = 2 if attempts == 1 else 3 if attempts == 2 else 5
                weighted_ids.extend([word_id] * weight)
            else:
                weighted_ids.append(word_id)

    random.shuffle(weighted_ids)
    return list(dict.fromkeys(weighted_ids))[:num_words]

# ============================================================
# WORD LIST HELPERS
# ============================================================

def load_word_list(filename):
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), "r", encoding="utf-8") as f:
            return [line.strip() for line in f]
    except Exception as e:
        print("[WORD LIST ERROR]", e)
        return []

# ============================================================
# GLOBAL STATE (SESSION-LOCAL)
# ============================================================

current_word_idx = 0
main_contest_words = []
main_contest_word_IDS = []
wrong_words = []
filename = None

badwords = ["unwittingly", "masculinity", "crampons", "Erlenmeyer flask", "metabolically", "exclusivity", "klutzy", "expostulatory", "Wilderness Road", "peregrinator", "eeriest", "emaciation", "Tyrrhenian Sea", "epistemologist", "Russophobia", "missa cantata", "nightmarishly", "verde antique", "debauched", "noteworthiness", "tonka bean", "Catch-22, catch-22", "agronomic", "minimization", "fortidudinous", "Nazification", "discomfited", "Louis Quatorze", "confabulation", "Himalaya Mountains", "pas de deux", "breviaries", "mismanagement", "ostensibly", "esprit de corps", "pseudonymous", "calibrator", "disengagement", "panacean", "condolatory", "deforestation", "compensatory", "Jekyll and Hyde", "euphoric", "permissibility", "fungicidal", "minute of arc", "herpetologist", "khapra beetle", "ferocity", "allurement", "prima donna", "infallibility", "electability", "afforestation", "extortioner", "admissibility", "chambered nautilus", "subornation", "mobocratic", "hoisin sauce", "Creutzfeldt-Jakob disease", "dinosaurian", "submergence", "sanctum sanctorum", "caveat emptor", "Stanford-Binet test", "infallibility", "xeroderma pigmentosum", "transitionary", "grievousness", "destabilization", "Qattara Depression", "brotherliness", "queued", "cingulate", "creativity", "comelier", "interleukin-1", "in vivo", "Snellen chart", "Komodo dragon", "manorial", "disinterred", "Ferris wheel", "proclivities", "assurgency", "indecisiveness", "Pillars of Hercules", "reunification", "ravening", "stippled", "unification", "Pavlovian", "amphorae", "Wahhabism", "foramina", "genealogist", "outsourcing", "chronicled", "sarcoptic mange", "maceration", "Malthusian", "predominately", "scoundrelly", "obsolescence", "recidivist", "offensiveness", "validation", "organically", "enigmatical", "San Andreas Fault", "arraignment", "nonexistent", "Van Allen belt", "amnesiac"]

# ============================================================
# AUDIO HELPERS
# ============================================================

def generate_and_play_word_alternate(word):
    tts = gTTS(text=word, lang="en")
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    tts.save(tmp.name)
    data = open(tmp.name, "rb").read()
    os.remove(tmp.name)
    return data


def get_and_play_word(wordNum):
    base = os.path.join(os.path.dirname(__file__), "audiofiles")

    if 0 < wordNum <= 500:
        folder = os.path.join(base, "500")
    elif 500 < wordNum <= 1000:
        folder = os.path.join(base, "1000")
    elif 1000 < wordNum <= 1500:
        folder = os.path.join(base, "1500")
    else:
        folder = base

    wav = os.path.join(folder, f"{wordNum}.wav")
    mp3 = os.path.join(folder, f"{wordNum}.mp3")
    fallback = os.path.join(base, "noxious.mp3")

    try:
        return open(wav, "rb").read()
    except Exception:
        try:
            return open(mp3, "rb").read()
        except Exception:
            return open(fallback, "rb").read()

# ============================================================
# WORD CHECKING
# ============================================================

def check_word(user_input):
    global current_word_idx, main_contest_words

    if current_word_idx >= len(main_contest_words):
        return False

    _, raw_word = main_contest_words[current_word_idx]
    correct_words = [w.strip() for w in raw_word.split("(")[0].split(",")]
    user_inputs = [w.strip() for w in user_input.split(",")]

    if all(ui in correct_words for ui in user_inputs):
        return True

    return f"Incorrect. Correct answer: {', '.join(correct_words)}"

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET", "POST"])
def index():
    global current_word_idx, main_contest_words, main_contest_word_IDS, wrong_words, filename

    file_names = [
        "2025.txt", "2024.txt", "2023.txt", "2022.txt",
        "2021.txt", "2020.txt", "2019.txt", "missedwords.txt"
    ]

    if request.method == "POST":
        filename = request.form["filename"]
        start_index = int(request.form["start_index"])
        end_index = int(request.form["end_index"])
        num_words = int(request.form["num_words"])

        word_list = load_word_list(filename)
        if not word_list:
            return render_template("index.html", file_names=file_names)

        if filename == "missedwords.txt":
            main_contest_word_IDS = list(range(start_index, min(end_index + 1, len(word_list) + 1)))
            random.shuffle(main_contest_word_IDS)
            main_contest_word_IDS = main_contest_word_IDS[:num_words]
        else:
            main_contest_word_IDS = rng_word_ids_with_weighting(
                word_list, start_index, end_index, num_words
            )

        main_contest_words = [
            (i, word_list[i - 1]) for i in main_contest_word_IDS if 0 < i <= len(word_list)
        ]

        current_word_idx = 0
        wrong_words = []

        audio_data = get_and_play_word(main_contest_word_IDS[0])
        return render_template(
            "contest.html",
            current_word_idx=0,
            total_words=len(main_contest_words),
            feedback=None,
            audio_data=audio_data
        )

    return render_template("index.html", file_names=file_names)


@app.route("/contest", methods=["POST"])
def contest():
    global current_word_idx, wrong_words

    user_input = request.form["user_input"]
    feedback = check_word(user_input)

    if feedback is True:
        current_word_idx += 1
    else:
        _, raw_word = main_contest_words[current_word_idx]
        add_missed_word(raw_word.split("(")[0].strip())
        wrong_words.append((main_contest_words[current_word_idx], user_input))

    if current_word_idx < len(main_contest_words):
        audio_data = get_and_play_word(main_contest_word_IDS[current_word_idx])
        return render_template(
            "contest.html",
            current_word_idx=current_word_idx,
            total_words=len(main_contest_words),
            feedback=feedback,
            audio_data=audio_data,
            wrong_words=wrong_words
        )

    return redirect(url_for("index"))


@app.route("/pronounce")
def pronounce_word():
    _, raw_word = main_contest_words[current_word_idx]

    if raw_word in badwords or filename == "missedwords.txt":
        audio_data = generate_and_play_word_alternate(raw_word)
    else:
        audio_data = get_and_play_word(main_contest_word_IDS[current_word_idx])

    return send_file(
        io.BytesIO(audio_data),
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="pronunciation.mp3"
    )

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
