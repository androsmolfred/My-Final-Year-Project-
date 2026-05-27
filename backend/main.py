# main.py — PRODUCTION-READY BACKEND
# Run with: python main.py
# main.py — FIXED: targets your exact plate misreads

import cv2
import numpy as np
import re
import os
import sqlite3
import tempfile
import traceback
import json
from datetime import datetime, timedelta
from collections import Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
from ultralytics import YOLO

app = Flask(__name__)
CORS(app)

# ================================================================
#  MODEL LOADING (2 YOLO MODELS)
# ================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "live_data.db")
LIVE_MAX = 200
LIVE_RETENTION_SECONDS = 60 * 60

YOLO1_PATH = os.path.join(BASE_DIR, "best.pt")
YOLO2_PATH = os.path.join(BASE_DIR, "best_2.pt")

print("[STARTUP] Loading YOLO models...")
yolo_models = []
for path, name in [(YOLO1_PATH, "best.pt"), (YOLO2_PATH, "best_2.pt")]:
    try:
        if not os.path.exists(path):
            print(f"[STARTUP] ⚠️ {name} not found at: {path} (skipping)")
            continue
        m = YOLO(path)
        yolo_models.append(m)
        print(f"[STARTUP] ✅ YOLO loaded: {name}")
    except Exception as e:
        print(f"[STARTUP] ❌ YOLO failed to load {name}: {e}")

if not yolo_models:
    print("[STARTUP] ❌ No YOLO models loaded. Detection will fail.")

# ================================================================
#  OCR ENGINE (EasyOCR Only)
# ================================================================
print("[STARTUP] Loading EasyOCR...")
easy_ocr = None
try:
    import easyocr
    easy_ocr = easyocr.Reader(['en'], gpu=False, verbose=False)
    print("[STARTUP] ✅ EasyOCR loaded")
except Exception as e:
    print(f"[STARTUP] ⚠️ EasyOCR failed: {e}")

engines_loaded = 1 if easy_ocr is not None else 0
print(f"[STARTUP] {engines_loaded} OCR engine loaded\n")


# ================================================================
#  LIVE DATA STORAGE (SQLite)
# ================================================================
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT,
                plate_key TEXT,
                state TEXT,
                confidence REAL,
                filename TEXT,
                source TEXT,
                timestamp_utc TEXT,
                raw_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_live_detections_plate_key_source ON live_detections(plate_key, source)"
        )
        conn.commit()
    finally:
        conn.close()


init_db()


def normalize_plate_key(plate):
    if not plate:
        return None
    cleaned = re.sub(r'[^A-Z0-9]', '', str(plate).upper())
    return cleaned if cleaned else None


def cleanup_expired_detections(conn):
    cutoff = (datetime.utcnow() - timedelta(seconds=LIVE_RETENTION_SECONDS)).isoformat(sep=' ', timespec='seconds')
    conn.execute(
        "DELETE FROM live_detections WHERE updated_at < ?",
        (cutoff,)
    )
    conn.commit()


def get_live_detections(limit=LIVE_MAX):
    conn = db_connect()
    try:
        cleanup_expired_detections(conn)
        rows = conn.execute(
            "SELECT plate_number, state, confidence, filename, source, timestamp_utc FROM live_detections ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_or_update_live_detection(payload):
    plate_number = payload.get("plate_number") or payload.get("plate") or "Unknown"
    plate_key = normalize_plate_key(plate_number)
    source = payload.get("source") or "live-camera"
    state = payload.get("state_of_origin") or payload.get("state") or payload.get("detected_state") or "Unknown"
    confidence = float(payload.get("confidence") or payload.get("yolo_conf") or 0.0)
    filename = payload.get("filename") or "live-camera"
    timestamp_utc = datetime.utcnow().isoformat() + 'Z'
    raw_json = json.dumps(payload, default=str)

    conn = db_connect()
    try:
        cleanup_expired_detections(conn)
        existing = None
        if plate_key:
            existing = conn.execute(
                "SELECT id, confidence FROM live_detections WHERE plate_key = ? AND source = ?",
                (plate_key, source)
            ).fetchone()

        if existing:
            should_update = confidence >= existing["confidence"]
            if should_update:
                conn.execute(
                    "UPDATE live_detections SET plate_number = ?, state = ?, confidence = ?, filename = ?, timestamp_utc = ?, raw_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (plate_number, state, confidence, filename, timestamp_utc, raw_json, existing["id"])
                )
        else:
            conn.execute(
                "INSERT INTO live_detections (plate_number, plate_key, state, confidence, filename, source, timestamp_utc, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (plate_number, plate_key, state, confidence, filename, source, timestamp_utc, raw_json)
            )
        conn.commit()
    finally:
        conn.close()


# ================================================================
#  PLATE FORMAT + STATE DATA
# ================================================================
STRICT_PLATE = re.compile(r'^[A-Z]{3}\d{3}[A-Z]{2}$')

NOISE_WORDS = [
    "FEDERAL", "REPUBLIC", "NIGERIA", "CENTRE", "CENTER",
    "UNITY", "EXCELLENCE", "STATE", "GOVERNMENT", "OF",
]

STATE_NOISE = [
    "LAGOS", "ABUJA", "KANO", "RIVERS", "OGUN", "EDO", "DELTA",
    "ENUGU", "ANAMBRA", "KADUNA", "PLATEAU", "IMO", "AKWAIBOM",
    "CROSSRIVER", "BAYELSA", "BORNO", "NIGER", "KWARA", "EKITI",
    "OSUN", "ONDO", "KATSINA", "KEBBI", "SOKOTO", "ZAMFARA",
    "JIGAWA", "YOBE", "GOMBE", "ADAMAWA", "BAUCHI", "TARABA",
    "NASARAWA", "KOGI", "BENUE", "EBONYI", "OYO", "FCT",
]
ALL_NOISE = NOISE_WORDS + STATE_NOISE

DIGIT_TO_LETTER = {
    '0': 'O', '1': 'I', '2': 'Z', '3': 'B', '4': 'A',
    '5': 'S', '6': 'G', '7': 'T', '8': 'B', '9': 'D',
}
LETTER_TO_DIGIT = {
    'O': '0', 'I': '1', 'L': '1', 'Z': '2', 'B': '8',
    'S': '5', 'G': '6', 'T': '7', 'A': '4', 'E': '3',
}

LGA_PREFIX_DB = {
    # Abuja / FCT
    "ABC": ("Abuja", "Abuja Municipal"), "ABJ": ("Abuja", "Abuja Municipal"),
    "ABU": ("Abuja", "Abuja Municipal"), "AGW": ("Abuja", "Abaji"),
    "BWR": ("Abuja", "Bwari"), "GWA": ("Abuja", "Gwagwalada"),
    "KUJ": ("Abuja", "Kuje"), "KWL": ("Abuja", "Kwali"),
    "FCT": ("Abuja", "FCT"), "FGE": ("Abuja", "FCT"),

    # Lagos
    "AGL": ("Lagos", "Agege"), "APP": ("Lagos", "Apapa"),
    "BDG": ("Lagos", "Badagry"), "EPE": ("Lagos", "Epe"),
    "ETI": ("Lagos", "Eti-Osa"), "FST": ("Lagos", "Festac"),
    "GGE": ("Lagos", "Gbagada"), "IKD": ("Lagos", "Ikeja"),
    "IKJ": ("Lagos", "Ikeja"), "IKR": ("Lagos", "Ikorodu"),
    "JJJ": ("Lagos", "Ojo"), "JLG": ("Lagos", "Lagos Island"),
    "KJA": ("Lagos", "Ikeja"), "KSF": ("Lagos", "Kosofe"),
    "LAS": ("Lagos", "Lagos Island"), "LND": ("Lagos", "Lagos Mainland"),
    "LSD": ("Lagos", "Lagos State"), "LSR": ("Lagos", "Lagos State"),
    "MUS": ("Lagos", "Mushin"), "OJO": ("Lagos", "Ojo"),
    "OSH": ("Lagos", "Oshodi"), "SMK": ("Lagos", "Somolu"),
    "SUR": ("Lagos", "Surulere"), "YAB": ("Lagos", "Yaba"),
    "AAA": ("Lagos", "Lagos Central"), "LSG": ("Lagos", "Lagos State"),
    "EKY": ("Lagos", "Ikoyi"), "JIA": ("Lagos", "Ikeja"),

    # Oyo
    "IBA": ("Oyo", "Ibadan North"), "IBD": ("Oyo", "Ibadan"),
    "OGB": ("Oyo", "Ogbomosho"), "OYO": ("Oyo", "Oyo"),

    # Kano
    "KAN": ("Kano", "Kano Municipal"), "KMC": ("Kano", "Kano Municipal"),
    "FGG": ("Kano", "Fagge"), "DAL": ("Kano", "Dala"),

    # Rivers
    "PHC": ("Rivers", "Port Harcourt"), "RIV": ("Rivers", "Rivers"),
    "RGE": ("Rivers", "Rivers East"), "OBI": ("Rivers", "Obio-Akpor"),

    # Ogun
    "ABK": ("Ogun", "Abeokuta"), "OTA": ("Ogun", "Ota"),
    "IJB": ("Ogun", "Ijebu Ode"),

    # Others
    "BEN": ("Edo", "Benin City"), "EDS": ("Edo", "Edo State"),
    "ASB": ("Delta", "Asaba"), "WAR": ("Delta", "Warri"),
    "ENU": ("Enugu", "Enugu"), "NSK": ("Enugu", "Nsukka"),
    "AWK": ("Anambra", "Awka"), "ONT": ("Anambra", "Onitsha"),
    "KAD": ("Kaduna", "Kaduna"), "ZRA": ("Kaduna", "Zaria"),
    "JOS": ("Plateau", "Jos"), "PLT": ("Plateau", "Plateau"),
    "OWE": ("Imo", "Owerri"), "UYO": ("AkwaIbom", "Uyo"),
    "CAL": ("CrossRiver", "Calabar"), "CRS": ("CrossRiver", "Cross River"),
    "YEN": ("Bayelsa", "Yenagoa"), "MAI": ("Borno", "Maiduguri"),
    "MIN": ("Niger", "Minna"), "ILR": ("Kwara", "Ilorin"),
    "ADE": ("Ekiti", "Ado Ekiti"), "OSG": ("Osun", "Osogbo"),
    "IFE": ("Osun", "Ile-Ife"), "AKR": ("Ondo", "Akure"),
    "KAT": ("Katsina", "Katsina"), "SOK": ("Sokoto", "Sokoto"),
    "GUS": ("Zamfara", "Gusau"), "DUT": ("Jigawa", "Dutse"),
    "DAM": ("Yobe", "Damaturu"), "GMB": ("Gombe", "Gombe"),
    "YOL": ("Adamawa", "Yola"), "BAU": ("Bauchi", "Bauchi"),
    "JAL": ("Taraba", "Jalingo"), "LAF": ("Nasarawa", "Lafia"),
    "LOK": ("Kogi", "Lokoja"), "MKD": ("Benue", "Makurdi"),
    "ABA": ("Ebonyi", "Abakaliki"),
}
VALID_PREFIXES = set(LGA_PREFIX_DB.keys())


# ================================================================
#  IMAGE PREPROCESSING
# ================================================================
def preprocess_plate(img):
    variants = []
    h, w = img.shape[:2]
    scale = 1.0
    if w < 200: scale = 200.0 / w
    if h < 60: scale = max(scale, 60.0 / h)
    if scale > 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants.append(gray)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    clahe_img = clahe.apply(gray)
    variants.append(clahe_img)

    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)
    variants.append(cv2.bitwise_not(otsu))

    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(clahe_img, -1, kernel)
    variants.append(sharpened)

    adapt = cv2.adaptiveThreshold(
        clahe_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 8
    )
    variants.append(adapt)

    result = []
    for v in variants:
        if len(v.shape) == 2:
            result.append(cv2.cvtColor(v, cv2.COLOR_GRAY2BGR))
        else:
            result.append(v)
    return result


def safe_crop(image, y1, y2, x1, x2, pad=20):
    h, w = image.shape[:2]
    return image[max(0, y1 - pad):min(h, y2 + pad),
                 max(0, x1 - pad):min(w, x2 + pad)]


def split_plate_regions(img):
    h = img.shape[0]
    if h < 10: return img, img, img
    top    = img[0:int(h * 0.25), :]
    middle = img[int(h * 0.15):int(h * 0.85), :]
    bottom = img[int(h * 0.75):, :]
    return top, middle, bottom


# ================================================================
#  OCR RUNNER (EasyOCR)
# ================================================================
def run_easyocr(img):
    if easy_ocr is None:
        return []
    try:
        result = easy_ocr.readtext(img, detail=0,
                                   allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
        return [t.strip().upper() for t in result if isinstance(t, str) and t.strip()]
    except Exception as e:
        print(f"  [EasyOCR error] {e}")
        return []


def run_all_engines(img):
    variants = preprocess_plate(img)
    easy_texts = []
    for v in variants:
        easy_texts.extend(run_easyocr(v))

    seen = set()
    deduped = [x for x in easy_texts if x not in seen and not seen.add(x)]
    return deduped, {"easy": deduped}


# ================================================================
#  PREFIX LOOKUP
# ================================================================
def levenshtein(a, b):
    if len(a) < len(b): return levenshtein(b, a)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        cur = [i + 1]
        for j, cb in enumerate(b):
            cur.append(min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (ca != cb)))
        prev = cur
    return prev[-1]


def lookup_prefix(cp):
    if not cp or len(cp) < 3:
        return (cp or ""), 99, "Unknown", "Unknown"
    cp = cp[:3].upper()
    if cp in VALID_PREFIXES:
        s, l = LGA_PREFIX_DB[cp]
        return cp, 0, s, l
    best, best_d = None, 99
    for p in VALID_PREFIXES:
        d = levenshtein(cp, p)
        if d < best_d:
            best, best_d = p, d
            if d == 0: break
    if best and best_d == 1:
        s, l = LGA_PREFIX_DB[best]
        return best, 1, s, l
    return cp, 99, "Unknown", "Unknown"


# ================================================================
#  PLATE EXTRACTION (STRICTER QUALITY GATES)
# ================================================================
def clean_ocr_text(text):
    t = text.upper()
    for w in ALL_NOISE:
        t = t.replace(w, ' ')
    return re.sub(r'\s+', ' ', t).strip()


def force_lll_ddd_ll(chars):
    """
    Force ANY 8-char string into LLL-DDD-LL format.
    Returns None if more than 2 unknowns (likely garbage from noisy frames).
    """
    if len(chars) < 8:
        chars = chars.ljust(8, '0')

    out = []
    unknown_count = 0

    for i, ch in enumerate(chars[:8]):
        if i < 3 or i >= 6:  # letter positions
            if ch.isdigit():
                out.append(DIGIT_TO_LETTER.get(ch, 'A'))
            elif ch.isalpha():
                out.append(ch)
            else:
                out.append('A')
                unknown_count += 1
        else:  # digit positions
            if ch.isdigit():
                out.append(ch)
            elif ch in LETTER_TO_DIGIT:
                out.append(LETTER_TO_DIGIT[ch])
            else:
                out.append('0')
                unknown_count += 1

    if unknown_count > 2:
        return None
    return "".join(out)


def _try_extract_8chars(raw_text):
    chars = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
    if len(chars) < 8:
        return None
    corrected = force_lll_ddd_ll(chars[:8])
    if not corrected or not STRICT_PLATE.match(corrected):
        return None

    mp, dist, state, lga = lookup_prefix(corrected[:3])
    final = mp + corrected[3:] if dist <= 1 else corrected
    if dist > 1:
        state, lga = "Unknown", "Unknown"
    if not STRICT_PLATE.match(final):
        final = corrected

    plate = f"{final[:3]}-{final[3:6]}-{final[6:8]}"
    score = 15 + sum(1 for a, b in zip(chars[:8], final) if a == b)
    if dist == 0:
        score += 20
    elif dist == 1:
        score += 8
    return (plate, score, dist, state, lga)


def extract_plate_from_texts(texts, debug_log=None):
    log = debug_log if debug_log is not None else []
    if not texts:
        log.append("  ⛔ No OCR texts provided")
        return ("", 0, 99, "Unknown", "Unknown")

    # Drop OCR noise (< 4 alphanumeric chars)
    clean_texts = [
        t for t in texts
        if t and len(re.sub(r'[^A-Z0-9]', '', t.upper())) >= 4
    ]
    if not clean_texts:
        log.append("  ⛔ All texts too short (< 4 chars)")
        return ("", 0, 99, "Unknown", "Unknown")

    log.append(f"  📥 Input: {len(clean_texts)} usable texts → {clean_texts[:8]}")
    candidates = []

    # Phase 1: Sliding window on each text
    for raw in clean_texts:
        chars = re.sub(r'[^A-Z0-9]', '', clean_ocr_text(raw).upper())
        if len(chars) < 6:
            continue
        for start in range(max(1, len(chars) - 7)):
            window = chars[start:start + 8]
            if len(window) == 8:
                res = _try_extract_8chars(window)
                if res:
                    candidates.append(res)

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        log.append(f"  ✅ Phase 1 → {candidates[0][0]} (score={candidates[0][1]})")
        return candidates[0]

    # Phase 2: Combined texts
    combined = re.sub(r'[^A-Z0-9]', '', clean_ocr_text(' '.join(clean_texts)))
    if len(combined) >= 8:
        for start in range(max(1, len(combined) - 7)):
            window = combined[start:start + 8]
            if len(window) == 8:
                res = _try_extract_8chars(window)
                if res:
                    candidates.append(res)

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        log.append(f"  ✅ Phase 2 → {candidates[0][0]} (score={candidates[0][1]})")
        return candidates[0]

    # Phase 3: Force format on each text >= 6 chars
    for raw in clean_texts:
        chars = re.sub(r'[^A-Z0-9]', '', raw.upper())
        if len(chars) >= 6:
            padded = chars[:8].ljust(8, '0')
            corrected = force_lll_ddd_ll(padded)
            if corrected and STRICT_PLATE.match(corrected):
                mp, dist, st, lg = lookup_prefix(corrected[:3])
                final = mp + corrected[3:] if dist <= 1 else corrected
                if dist > 1:
                    st, lg = "Unknown", "Unknown"
                if not STRICT_PLATE.match(final):
                    final = corrected
                plate = f"{final[:3]}-{final[3:6]}-{final[6:8]}"
                log.append(f"  ✅ Phase 3 → {plate}")
                return (plate, 8, dist, st, lg)

    # Removed previous Phase 4 & 5 — they invented garbage from noise frames
    log.append("  ⛔ No reliable plate found")
    return ("", 0, 99, "Unknown", "Unknown")


def extract_state_from_text(text):
    clean = text.upper().replace(" ", "")
    state_kw = {
        "LAGOS": "Lagos", "ABUJA": "Abuja", "KANO": "Kano",
        "RIVERS": "Rivers", "OGUN": "Ogun", "EDO": "Edo",
        "DELTA": "Delta", "ENUGU": "Enugu", "ANAMBRA": "Anambra",
        "KADUNA": "Kaduna", "IMO": "Imo", "OYO": "Oyo",
        "BAUCHI": "Bauchi", "BORNO": "Borno", "PLATEAU": "Plateau",
        "ONDO": "Ondo", "OSUN": "Osun", "EKITI": "Ekiti",
        "KOGI": "Kogi", "BENUE": "Benue", "TARABA": "Taraba",
        "SOKOTO": "Sokoto", "KEBBI": "Kebbi", "ZAMFARA": "Zamfara",
        "KATSINA": "Katsina", "JIGAWA": "Jigawa", "YOBE": "Yobe",
        "GOMBE": "Gombe", "NIGER": "Niger", "KWARA": "Kwara",
        "NASARAWA": "Nasarawa", "EBONYI": "Ebonyi", "BAYELSA": "Bayelsa",
    }
    for kw, st in state_kw.items():
        if kw in clean:
            return st
    return "Unknown"


# ================================================================
#  YOLO & CONFIDENCE
# ================================================================
def detect_best_plate_box(frame):
    if not yolo_models:
        return None, 0.0
    best_box, best_conf = None, -1.0
    for model in yolo_models:
        for imgsz in [640, 1280]:
            try:
                dets = model(frame, imgsz=imgsz, verbose=False, conf=0.10)
                boxes = dets[0].boxes if dets else []
            except Exception:
                continue
            for b in boxes:
                try:
                    conf = float(b.conf[0])
                    if conf > best_conf:
                        best_conf = conf
                        best_box = b
                except Exception:
                    continue
    if best_box is None:
        return None, 0.0
    return best_box, best_conf * 100


def compute_confidence(yolo_conf, plate_score, prefix_dist, engines_agreed, plate_valid):
    if not plate_valid:
        return 0.0
    base   = min(yolo_conf * 0.35, 35.0)
    ocr    = min(plate_score * 0.5, 30.0)
    prefix = 15.0 if prefix_dist == 0 else (7.0 if prefix_dist == 1 else 2.0)
    agree  = min(engines_agreed * 10.0, 10.0)
    total  = max(35.0, min(base + ocr + prefix + agree, 92.0))
    return round(total, 1)


# ================================================================
#  DEDUPLICATION
# ================================================================
def plate_is_duplicate(plate, seen):
    if not plate or plate == "Not Found":
        return False
    clean = re.sub(r'[^A-Z0-9]', '', plate.upper())
    if len(clean) != 8:
        return plate in seen
    key = clean[:3] + "*" + clean[6:8]
    for sp in seen:
        spc = re.sub(r'[^A-Z0-9]', '', sp.upper())
        if len(spc) == 8 and spc[:3] + "*" + spc[6:8] == key:
            return True
    return False


# ================================================================
#  FRAME PROCESSOR
# ================================================================
def _make_result(label, msg="Not Found", yolo_conf=0.0, debug=None):
    return {
        "filename": label,
        "plate_number": "Not Found",
        "state_of_origin": "Unknown",
        "detected_state": "Unknown",
        "lga": "Unknown",
        "confidence": 0.0,
        "yolo_conf": round(yolo_conf, 2),
        "format_valid": False,
        "format_message": msg,
        "plate_format": "INVALID",
        "state_match": False,
        "lgas": [],
        "raw_ocr_middle": "",
        "raw_ocr_top": "",
        "raw_ocr_bottom": "",
        "ocr_engines": {},
        "debug_log": debug or [],
    }


def process_frame(frame, label=""):
    debug = [f"Image: {label}"]
    if not yolo_models:
        return _make_result(label, "YOLO models not loaded", debug=debug)
    if engines_loaded == 0:
        return _make_result(label, "OCR engine not loaded", debug=debug)

    best_box, yolo_conf = detect_best_plate_box(frame)
    all_texts = []
    eng_dict = {"easy": []}
    crop_used = "N/A"
    ocr_state_text = "Unknown"

    if best_box is not None:
        x1, y1, x2, y2 = map(int, best_box.xyxy[0])
        debug.append(f"🎯 YOLO: {yolo_conf:.1f}% box=({x1},{y1}→{x2},{y2})")

        crop = safe_crop(frame, y1, y2, x1, x2, pad=20)
        if crop.size > 0:
            ch, cw = crop.shape[:2]
            crop_used = f"{cw}×{ch}"
            top_r, mid_r, bot_r = split_plate_regions(crop)

            top_texts, _ = run_all_engines(top_r)
            mid_texts, mid_eng = run_all_engines(mid_r)
            bot_texts, _ = run_all_engines(bot_r)
            full_texts, full_eng = run_all_engines(crop)

            all_texts = mid_texts + full_texts + top_texts + bot_texts
            ocr_state_text = extract_state_from_text(" ".join(all_texts))
            eng_dict["easy"] = list(dict.fromkeys(
                mid_eng.get("easy", []) + full_eng.get("easy", [])
            ))
    else:
        debug.append("⚠️ YOLO: no detection → full-frame OCR")
        all_texts, eng_dict = run_all_engines(frame)
        crop_used = "full-frame"

    plate_num, plate_score, prefix_dist, state, lga = \
        extract_plate_from_texts(all_texts, debug)

    if not plate_num:
        plate_num = "Not Found"
    if state == "Unknown" and ocr_state_text != "Unknown":
        state = ocr_state_text

    is_fmt = plate_num not in ("Not Found", "")
    is_strict = bool(STRICT_PLATE.match(re.sub(r'[^A-Z0-9]', '', plate_num.upper()))) if is_fmt else False

    engines_agreed = 0
    if is_fmt:
        pchars = re.sub(r'[^A-Z0-9]', '', plate_num)
        for t in eng_dict.get("easy", []):
            tc = re.sub(r'[^A-Z0-9]', '', t)
            if len(tc) >= 5 and sum(1 for a, b in zip(tc[:8], pchars[:8]) if a == b) >= 5:
                engines_agreed += 1
                break

    conf = compute_confidence(
        yolo_conf,
        plate_score if is_fmt else 0,
        prefix_dist if is_fmt else 99,
        engines_agreed,
        is_fmt
    )

    return {
        "filename": label,
        "plate_number": plate_num,
        "state_of_origin": state,
        "detected_state": state,
        "lga": lga if is_fmt else "Unknown",
        "confidence": conf,
        "yolo_conf": round(yolo_conf, 2),
        "format_valid": is_fmt,
        "format_message": (
            "Verified LGA prefix" if (is_strict and prefix_dist == 0)
            else ("Near-match LGA" if (is_strict and prefix_dist == 1)
            else ("Strict format" if is_strict
            else ("Partial read" if is_fmt else "Not matched")))
        ),
        "plate_format": "LLL-DDD-LL" if is_strict else ("RAW" if is_fmt else "INVALID"),
        "state_match": state != "Unknown",
        "lgas": [lga] if lga != "Unknown" else [],
        "ocr_engines": eng_dict,
        "debug_log": debug,
        "debug_crop": crop_used,
    }


# ================================================================
#  API ROUTES
# ================================================================
@app.route("/", methods=["GET"])
def api_root():
    return jsonify({
        "status": "online",
        "service": "AVLPRDL Engine",
        "diagnostic": "/api/diagnose"
    }), 200

# =========================
# API ROUTES
# =========================

@app.route("/api/test", methods=["GET"])
def api_test():
    return jsonify({
        "status": "ok",
        "yolo_models_loaded": len(yolo_models),
        "easy": easy_ocr is not None,
        "engines_loaded": engines_loaded,
        "lga_prefixes": len(VALID_PREFIXES)
    }), 200


@app.route("/api/process-image", methods=["POST"])
def api_process_image():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file field"}), 400
        upload = request.files["file"]
        data = np.frombuffer(upload.read(), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Cannot decode image"}), 400
        return jsonify(process_frame(img, upload.filename or "image")), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 200


@app.route("/api/process-video", methods=["POST"])
def api_process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file field"}), 400

    upload = request.files["file"]
    ext = os.path.splitext(upload.filename or "video")[-1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

    try:
        upload.save(tmp.name)
        tmp.close()
    except Exception as e:
        return jsonify({"error": f"Save failed: {e}"}), 500

    try:
        skip = int(request.form.get("skip_frames", 10))
        maxf = int(request.form.get("max_frames", 100))
        cap = cv2.VideoCapture(tmp.name)

        if not cap.isOpened():
            return jsonify({"error": "Cannot open video"}), 400

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or -1

        results = []
        seen_plates = []
        idx = 0
        proc = 0

        while proc < maxf and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if idx % skip == 0:
                proc += 1
                r = process_frame(frame, f"Frame {idx} ({idx/fps:.1f}s)")
                plate = r.get("plate_number", "Not Found")
                if plate not in ("Not Found", "", None):
                    duplicate = plate_is_duplicate(plate, seen_plates)
                    r["is_duplicate"] = duplicate
                    if not duplicate:
                        seen_plates.append(plate)
                results.append(r)
            idx += 1

        cap.release()

        valid = [r for r in results if r.get("plate_number") not in ("Not Found", "", None)]
        found = len(valid)
        best = max(valid, key=lambda r: r.get("confidence", 0)) if valid else None

        return jsonify({
            "total_frames": total,
            "processed_frames": proc,
            "plates_found": found,
            "unique_plates": len(seen_plates),
            "best_result": best,
            "results": results,
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


# ================================================================
#  DIAGNOSE / ALIASES / LIVE-CAMERA AUTO-LOG
# ================================================================
@app.route("/api/diagnose", methods=["POST"])
def api_diagnose():
    try:
        img = None
        if "file" in request.files:
            upload = request.files["file"]
            data = np.frombuffer(upload.read(), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Send image as 'file'"}), 400
        res = process_frame(img, "DIAGNOSTIC")
        res["status"] = "diagnostic_complete"
        return jsonify(res), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 200


def _get_file():
    for f in ("file", "frame", "video", "image"):
        if f in request.files:
            return request.files[f]
    return None


@app.route("/api/image", methods=["POST"])
def api_image():
    """
    Used by both image uploads and live camera frames.
    If field name is 'frame', treat as live camera and auto-log to SQLite.
    """
    try:
        upload = _get_file()
        if not upload:
            return jsonify({"error": "No file"}), 400

        data = np.frombuffer(upload.read(), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Cannot decode"}), 400

        # Detect if this is a live camera frame
        is_live_camera = "frame" in request.files
        label = upload.filename or ("Live Camera" if is_live_camera else "image")

        result = process_frame(img, label)

        # Auto-log live camera detections to SQLite
        if is_live_camera and result.get("plate_number") not in ("Not Found", "", None):
            try:
                add_or_update_live_detection({
                    "plate_number":    result["plate_number"],
                    "state_of_origin": result.get("state_of_origin", "Unknown"),
                    "confidence":      result.get("confidence", 0),
                    "filename":        "Live Camera",
                    "source":          "live-camera",
                })
                print(f"  💾 Logged live plate: {result['plate_number']} "
                      f"(conf={result.get('confidence')}%)")
            except Exception as e:
                print(f"  ⚠️ Failed to log live plate: {e}")

        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 200


@app.route("/api/video", methods=["POST"])
def api_video():
    return api_process_video()


@app.route("/api/connection-test", methods=["GET"])
def api_connection_test():
    return api_test()


@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    return jsonify({"total": 0, "states": {}, "avg_confidence": 0, "recent": []}), 200


@app.route("/api/live-data", methods=["GET"])
def api_live_data():
    try:
        all_detections = get_live_detections(LIVE_MAX)
        return jsonify({
            "recent": all_detections[:10],
            "live_detections": all_detections,
            "total": len(all_detections),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/live-data/add", methods=["POST"])
def api_live_data_add():
    data = request.get_json() if request.is_json else (request.form.to_dict() or request.values.to_dict() or {})
    if not data:
        return jsonify({"error": "No detection data provided"}), 400
    try:
        add_or_update_live_detection(data)
        recent = get_live_detections(10)
        return jsonify({"status": "ok", "message": "detection added", "recent": recent}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/export-analytics", methods=["GET"])
def api_export_analytics():
    try:
        all_detections = get_live_detections(LIVE_MAX)
        return jsonify({
            "data": all_detections,
            "summary": {"total_records": len(all_detections), "duplicates_filtered": 0}
        }), 200
    except Exception:
        return jsonify({"data": [], "summary": {"duplicates_filtered": 0}}), 200


@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    try:
        conn = db_connect()
        conn.execute("DELETE FROM live_detections")
        conn.commit()
        conn.close()
        return jsonify({"message": "Logs cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🚗  AVLPR-DL Backend — Nigerian Plate Recognition")
    print("  📋  5-pass OCR  |  Strict LLL-DDD-LL  |  Multi-candidate voting")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
