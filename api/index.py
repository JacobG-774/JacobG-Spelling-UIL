from flask import Flask, render_template, request, redirect, url_for, send_file
import random
from gtts import gTTS
import os
import tempfile
import io
import time
import json
import requests

# --------- JSONBin Configuration ---------
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")

JSONBIN_GET_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
JSONBIN_PUT_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# --------- Flask App ---------
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# --------- Missed Words (Mutable JSON) ---------
def load_missed_words():
    try:
        r = requests.get(
            JSONBIN_GET_URL,
            headers={"X-Master-Key": JSONBIN_API_KEY},
            timeout=5
        )
        if r.status_code == 200:
            return r.json()["record"].get("missed_words", [])
    except Exception as e:
        print("[JSONBIN LOAD ERROR]", e)
    return []

def save_missed_words(missed_words_list):
    try:
        r = requests.put(
            JSONBIN_PUT_URL,
            headers={
                "X-Master-Key": JSONBIN_API_KEY,
                "Content-Type": "application/json"
            },
            json={"missed_words": missed_words_list},
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
            save_missed_words(missed_words)
            return
    missed_words.append({
        "word": word,
        "attempts": 1,
        "correct": 0
    })
    save_missed_words(missed_words)

def remove_missed_word(word):
    missed_words = load_missed_words()
    updated = [w for w in missed_words if w["word"] != word]
    save_missed_words(updated)

def get_missed_words_dict():
    missed_words = load_missed_words()
    return {w["word"]: w["attempts"] for w in missed_words}

# --------- Weighted Selection ---------
def rng_word_ids_with_weighting(word_list, start_index, end_index, num_words, weight_missed=True):
    if not (1 <= start_index <= end_index <= 1500):
        return []
    missed_words_dict = get_missed_words_dict()
    weighted_ids = []
    for word_id in range(start_index, end_index + 1):
        if word_id <= len(word_list):
            word = word_list[word_id - 1].split("(")[0].strip()
            if weight_missed and word in missed_words_dict:
                attempts = missed_words_dict[word]
                weight = 2 if attempts == 1 else 3 if attempts == 2 else 5
                weighted_ids.extend([word_id] * weight)
            else:
                weighted_ids.append(word_id)
    random.shuffle(weighted_ids)
    return list(dict.fromkeys(weighted_ids))[:num_words]

# --------- Word List ---------
def load_word_list(filename):
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), "r", encoding="utf-8") as f:
            return [line.strip() for line in f]
    except Exception as e:
        print("[WORD LIST ERROR]", e)
        return []

current_word_idx = 0
main_contest_words = []
wrong_words = []
badwords = [...]  # unchanged

# --------- Pronunciation (unchanged) ---------
def generate_and_play_word_alternate(word):
    tts = gTTS(text=word, lang='en')
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    tts.save(tmp.name)
    data = open(tmp.name, 'rb').read()
    os.remove(tmp.name)
    return data

def get_and_play_word(wordNum):
    # unchanged
    ...

# --------- Word Checking (unchanged) ---------
def check_word(user_input):
    ...

# --------- Routes (unchanged) ---------
@app.route("/", methods=["GET", "POST"])
def index():
    ...

@app.route("/contest", methods=["GET", "POST"])
def contest():
    ...

@app.route("/pronounce")
def pronounce_word():
    ...

@app.route("/altpronounce")
def alt_pronounce_word():
    ...

if __name__ == "__main__":
    app.run(debug=True)


