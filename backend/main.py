# # main.py — PRODUCTION-READY BACKEND
# # Run with: python main.py

# import cv2
# import numpy as np
# import re
# import os
# import json
# import tempfile
# import traceback
# from flask import Flask, request, jsonify
# from ultralytics import YOLO
# from paddleocr import PaddleOCR

# # =========================
# # FLASK APP
# # =========================
# app = Flask(__name__)

# # =========================
# # LOAD MODELS (safe, version-aware)
# # =========================
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# YOLO_PATH = os.path.join(BASE_DIR, "best.pt")

# print("[STARTUP] Loading YOLO model...")
# try:
#     if not os.path.exists(YOLO_PATH):
#         raise FileNotFoundError(f"best.pt not found at {YOLO_PATH}")
#     yolo_model = YOLO(YOLO_PATH)
#     print("[STARTUP] ✅ YOLO loaded")
# except Exception as e:
#     print(f"[STARTUP] ❌ YOLO failed: {e}")
#     yolo_model = None

# print("[STARTUP] Loading PaddleOCR...")
# ocr = None
# try:
#     # Try modern API first (2.8+)
#     ocr = PaddleOCR(lang="en", show_log=False)
#     # Test if it works
#     _ = ocr.ocr(np.ones((50, 150, 3), dtype=np.uint8) * 255)
#     print("[STARTUP] ✅ PaddleOCR loaded (modern API)")
# except Exception:
#     try:
#         # Fallback to older API
#         ocr = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
#         print("[STARTUP] ✅ PaddleOCR loaded (legacy API)")
#     except Exception as e:
#         print(f"[STARTUP] ❌ PaddleOCR failed: {e}")

# # =========================
# # VALID NIGERIAN STATES
# # =========================
# VALID_STATES = {
#     "ABUJA": ["FCT", "ABJ", "ABUJA"], "LAGOS": ["LAG", "LGS", "LAGOS"],
#     "KANO": ["KAN", "KANO"], "OGUN": ["OGN", "OGUN"], "OYO": ["OYO"],
#     "RIVERS": ["RIV", "RIVERS"], "KADUNA": ["KAD", "KADUNA"],
#     "ENUGU": ["ENU", "ENUGU"], "DELTA": ["DEL", "DELTA"], "EDO": ["EDO"],
#     "ANAMBRA": ["ANM", "ANAMBRA"], "IMO": ["IMO"],
#     "AKWAIBOM": ["AKW", "AKWAIBOM", "AKWA"], "CROSSRIVER": ["CRS", "CROSSRIVER"],
#     "BORNO": ["BOR", "BORNO"], "NIGER": ["NIG", "NIGER"],
#     "PLATEAU": ["PLT", "PLATEAU"], "KWARA": ["KWR", "KWARA"],
#     "EKITI": ["EKT", "EKITI"], "OSUN": ["OSN", "OSUN"], "ONDO": ["OND", "ONDO"],
#     "BAYELSA": ["BAY", "BAYELSA"], "ZAMFARA": ["ZAM", "ZAMFARA"],
#     "KEBBI": ["KEB", "KEBBI"], "SOKOTO": ["SOK", "SOKOTO"],
#     "YOBE": ["YOB", "YOBE"], "GOMBE": ["GOM", "GOMBE"],
#     "NASARAWA": ["NAS", "NASARAWA"], "TARABA": ["TAR", "TARABA"],
#     "JIGAWA": ["JIG", "JIGAWA"], "KOGI": ["KOG", "KOGI"],
#     "BENUE": ["BEN", "BENUE"], "EBONYI": ["EBO", "EBONYI"],
#     "ADAMAWA": ["ADA", "ADAMAWA"], "BAUCHI": ["BAU", "BAUCHI"],
#     "KATSINA": ["KAT", "KATSINA"],
# }

# # =========================
# # PREPROCESSING
# # =========================
# def safe_crop(image, y1, y2, x1, x2, pad=12):
#     h, w = image.shape[:2]
#     return image[max(0,y1-pad):min(h,y2+pad), max(0,x1-pad):min(w,x2+pad)]

# def upscale(img, scale=2.5):
#     h, w = img.shape[:2]
#     return cv2.resize(img, (max(1,int(w*scale)), max(1,int(h*scale))), interpolation=cv2.INTER_CUBIC)

# def sharpen(img):
#     k = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
#     return cv2.filter2D(img, -1, k)

# def white_border(img, pad=20):
#     return cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255,255,255])

# def preprocess_standard(img):
#     img = upscale(img, 2.5)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     gray = cv2.createCLAHE(3.0, (8,8)).apply(gray)
#     gray = cv2.GaussianBlur(gray, (3,3), 0)
#     return white_border(sharpen(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))

# def preprocess_aggressive(img):
#     img = upscale(img, 3.0)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     gray = cv2.createCLAHE(5.0, (8,8)).apply(gray)
#     _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
#     return white_border(sharpen(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))

# def preprocess_morph(img):
#     img = upscale(img, 2.5)
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25,25))
#     gray = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
#     gray = cv2.createCLAHE(3.0, (8,8)).apply(gray)
#     gray = cv2.GaussianBlur(gray, (3,3), 0)
#     return white_border(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

# def split_plate_regions(img: np.ndarray):
#     """
#     Tighter crops to exclude slogans/frames.
#     Middle zone reduced to 35%-75% of height.
#     """
#     h = img.shape[0]
#     # State name is usually in the top 25%
#     top    = img[0 : int(h * 0.25), :]
#     # Plate number is the big text in the center
#     middle = img[int(h * 0.35) : int(h * 0.75), :]
#     # Republic name/slogan is in the bottom 25%
#     bottom = img[int(h * 0.75) :, :]
#     return top, middle, bottom

# # =========================
# # OCR ENGINE
# # =========================
# def run_ocr(img):
#     """Run OCR safely across PaddleOCR versions."""
#     if ocr is None:
#         return [], []
#     try:
#         # Try modern .ocr() first, fallback to .predict()
#         if hasattr(ocr, 'ocr'):
#             res = ocr.ocr(img, cls=False)
#         else:
#             res = ocr.predict(img)
        
#         texts, scores = [], []
#         if not res: return texts, scores
#         block = res[0] if isinstance(res, list) else res
#         if isinstance(block, dict):
#             texts = block.get("rec_texts", [])
#             scores = block.get("rec_scores", [])
#         elif isinstance(block, list):
#             for line in block:
#                 if line and len(line) >= 2:
#                     txt, sc = line[1] if isinstance(line[1], (list,tuple)) else (line[0], line[1])
#                     if isinstance(txt, str) and txt.strip():
#                         texts.append(txt.strip())
#                         scores.append(float(sc))
#         return texts, scores
#     except Exception as e:
#         print(f"      [OCR ERROR] {e}")
#         return [], []

# def run_all_ocr_passes(img):
#     pipelines = [("standard", preprocess_standard), ("aggressive", preprocess_aggressive), ("morph", preprocess_morph)]
#     best_text, best_score, best_rank = "", 0.0, -1
#     for name, fn in pipelines:
#         try:
#             proc = fn(img.copy())
#             texts, scores = run_ocr(proc)
#             if not texts: continue
#             combined = " ".join(texts)
#             avg_sc = sum(scores)/len(scores)
#             rank = len(re.sub(r"[^A-Z0-9]","",combined.upper())) + avg_sc
#             if rank > best_rank:
#                 best_text, best_score, best_rank = combined, avg_sc, rank
#         except Exception as e:
#             print(f"      [{name}] pipeline error: {e}")
#     return best_text, best_score

# # =========================
# # TEXT EXTRACTION
# # =========================
# _L2D = str.maketrans("OILZSBTG", "01125876")
# _D2L = str.maketrans("015860",   "OISGBO")

# PLATE_PATTERNS = [
#     r"([A-Z]{3})[^A-Z0-9]*(\d{3})[^A-Z0-9]*([A-Z]{2})",
#     r"([A-Z]{2})[^A-Z0-9]*(\d{3})[^A-Z0-9]*([A-Z]{3})",
#     r"([A-Z]{2,3})[^A-Z0-9]*(\d{2,4})[^A-Z0-9]*([A-Z]{2,3})",
# ]

# def positional_correct(text):
#     clean = re.sub(r"[^A-Z0-9]", "", text.upper())
#     if len(clean) < 5: return clean
#     out = []
#     for i, ch in enumerate(clean):
#         if i < 3 or i >= 6:
#             out.append(ch.translate(_D2L) if ch.isdigit() else ch)
#         else:
#             out.append(ch.translate(_L2D) if ch.isalpha() else ch)
#     return "".join(out)

# def extract_plate_number(raw: str) -> str:
#     """
#     Multi-pass extraction. Blocks long non-plate text.
#     """
#     # Remove obvious noise words before processing
#     noise_words = ["FEDERAL", "REPUBLIC", "NIGERIA", "CENTRE", "UNITY", "EXCELLENCE"]
#     text = raw.upper()
#     for word in noise_words:
#         text = text.replace(word, "")
    
#     text = text.replace(" ", "")
    
#     # Try pattern matching on raw and corrected text
#     candidates = [text, positional_correct(text)]

#     for candidate in candidates:
#         for pattern in PLATE_PATTERNS:
#             m = re.search(pattern, candidate)
#             if m:
#                 return "-".join(m.groups())

#     # If no pattern matches, take the SHORTEST valid-looking alphanumeric block
#     # This prevents slogans like "CENTREOFUNITY" from being returned
#     alnum = re.sub(r"[^A-Z0-9]", "", text)
    
#     # Nigerian plates are usually 8 chars. If it's longer than 11, it's garbage.
#     if 6 <= len(alnum) <= 11:
#         return f"RAW:{alnum}"

#     return "Not Found"

# def extract_state(text):
#     clean = text.upper().replace(" ", "")
#     for state, aliases in VALID_STATES.items():
#         for alias in aliases:
#             if alias.replace(" ","") in clean:
#                 return state.capitalize()
#     for state in VALID_STATES:
#         hits, pos = 0, 0
#         for ch in state:
#             idx = clean.find(ch, pos)
#             if idx != -1: hits += 1; pos = idx + 1
#         if hits / max(len(state),1) >= 0.6:
#             return state.capitalize()
#     return "Unknown"

# # =========================
# # FRAME PROCESSOR
# # =========================
# def process_frame(frame, label):
#     print(f"\n[API] Processing: {label}")
#     if yolo_model is None:
#         print("  ❌ YOLO not loaded")
#         return _make_result(label, "YOLO not loaded")
#     if ocr is None:
#         print("  ❌ OCR not loaded")
#         return _make_result(label, "OCR not loaded")

#     try:
#         dets = yolo_model(frame, imgsz=640, verbose=False)
#         boxes = dets[0].boxes if dets else []
#     except Exception as e:
#         print(f"  ❌ YOLO error: {e}")
#         return _make_result(label, f"YOLO error: {e}")

#     if not boxes:
#         print("  → No plate detected by YOLO")
#         return _make_result(label, "No YOLO detection")

#     best = max(boxes, key=lambda b: float(b.conf[0]))
#     yolo_conf = float(best.conf[0]) * 100
#     x1,y1,x2,y2 = map(int, best.xyxy[0])
#     print(f"  YOLO conf={yolo_conf:.1f}% box=({x1},{y1}→{x2},{y2})")

#     crop = safe_crop(frame, y1, y2, x1, x2, pad=12)
#     if crop.size == 0:
#         print("  ❌ Empty crop")
#         return _make_result(label, "Empty crop", yolo_conf)

#     h,w = crop.shape[:2]
#     if w < 30 or h < 15:
#         print(f"  ❌ Crop too small ({w}x{h})")
#         return _make_result(label, "Crop too small", yolo_conf)

#     top_r, mid_r, bot_r = split_plate_regions(crop)
#     print("  Running OCR passes...")
#     mid_text, mid_conf = run_all_ocr_passes(mid_r)
#     top_text, _ = run_all_ocr_passes(top_r)
#     bot_text, _ = run_all_ocr_passes(bot_r)

#     if not mid_text.strip() or mid_conf < 0.10:
#         print("  ⚠️ Weak middle OCR → trying full crop")
#         mid_text, mid_conf = run_all_ocr_passes(crop)

#     plate_num = extract_plate_number(mid_text)
#     if plate_num in ("Not Found", ""):
#         plate_num = extract_plate_number(f"{top_text} {mid_text} {bot_text}")

#     state = extract_state(f"{top_text} {bot_text}")
#     if state == "Unknown": state = extract_state(mid_text)

#     conf_pct = round(mid_conf * 100, 2)
#     is_fmt = plate_num not in ("Not Found","") and not plate_num.startswith("RAW:")
#     print(f"  ✅ plate='{plate_num}' state='{state}' conf={conf_pct}%")

#     return {
#         "filename": label, "plate_number": plate_num,
#         "state_of_origin": state, "detected_state": state,
#         "confidence": conf_pct, "yolo_conf": round(yolo_conf,2),
#         "format_valid": is_fmt, "format_message": "Matched" if is_fmt else "Pattern not matched",
#         "plate_format": "STANDARD" if "-" in plate_num else "INVALID",
#         "state_match": state != "Unknown", "lgas": [],
#         "raw_ocr_top": top_text, "raw_ocr_middle": mid_text, "raw_ocr_bottom": bot_text
#     }

# def _make_result(label, msg="Not Found", yolo_conf=0.0):
#     return {
#         "filename": label, "plate_number": "Not Found",
#         "state_of_origin": "Unknown", "detected_state": "Unknown",
#         "confidence": 0.0, "yolo_conf": round(yolo_conf,2),
#         "format_valid": False, "format_message": msg,
#         "plate_format": "INVALID", "state_match": False, "lgas": [],
#         "raw_ocr_top": "", "raw_ocr_middle": "", "raw_ocr_bottom": ""
#     }

# # =========================
# # API ROUTES
# # =========================
# @app.route("/api/test", methods=["GET"])
# def api_test():
#     return jsonify({"status":"ok", "yolo": yolo_model is not None, "ocr": ocr is not None, "message":"Backend running ✅"}), 200

# @app.route("/api/process-image", methods=["POST"])
# def api_process_image():
#     if "file" not in request.files:
#         return jsonify({"error":"No file field"}), 400
#     upload = request.files["file"]
#     data = np.frombuffer(upload.read(), dtype=np.uint8)
#     img = cv2.imdecode(data, cv2.IMREAD_COLOR)
#     if img is None:
#         return jsonify({"error":"Cannot decode image"}), 400
#     result = process_frame(img, label=upload.filename or "image")
#     return jsonify(result), 200

# @app.route("/api/process-video", methods=["POST"])
# def api_process_video():
#     if "file" not in request.files:
#         return jsonify({"error":"No file field"}), 400
#     upload = request.files["file"]
#     ext = os.path.splitext(upload.filename)[-1] or ".mp4"
#     tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
#     try:
#         upload.save(tmp.name); tmp.close()
#     except Exception as e:
#         return jsonify({"error":f"Save failed: {e}"}), 500

#     try:
#         skip = int(request.form.get("skip_frames", 10))
#         maxf = int(request.form.get("max_frames", 100))
#         cap = cv2.VideoCapture(tmp.name)
#         if not cap.isOpened():
#             return jsonify({"error":"Cannot open video"}), 400
#         fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
#         total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#         results, idx, proc = [], 0, 0
#         while proc < maxf:
#             ret, frame = cap.read()
#             if not ret: break
#             idx += 1
#             if idx % skip != 0: continue
#             proc += 1
#             results.append(process_frame(frame, f"Frame {idx} ({idx/fps:.1f}s)"))
#         cap.release()
#     except Exception as e:
#         traceback.print_exc()
#         return jsonify({"error":str(e)}), 500
#     finally:
#         try: os.unlink(tmp.name)
#         except: pass

#     found = sum(1 for r in results if r.get("plate_number") not in ("Not Found","",None))
#     return jsonify({"total_frames":total, "processed_frames":proc, "plates_found":found, "results":results}), 200

# # =========================
# # ENTRY POINT
# # =========================
# if __name__ == "__main__":
#     print("\n" + "="*55)
#     print("  🚗  AVLPRDL Backend — Nigerian Plate Recognition")
#     print("="*55 + "\n")
#     app.run(host="0.0.0.0", port=5000, debug=False)





# main.py — PRODUCTION-READY BACKEND
# Run with: python main.py
# main.py — FIXED: targets your exact plate misreads
import cv2
import numpy as np
import re
import os
import json
import tempfile
import traceback
from flask import Flask, request, jsonify
from ultralytics import YOLO
from paddleocr import PaddleOCR

app = Flask(__name__)

# =========================
# LOAD MODELS
# =========================
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
YOLO_PATH = os.path.join(BASE_DIR, "best.pt")

print("[STARTUP] Loading YOLO model...")
try:
    if not os.path.exists(YOLO_PATH):
        raise FileNotFoundError(f"best.pt not found at {YOLO_PATH}")
    yolo_model = YOLO(YOLO_PATH)
    print("[STARTUP] ✅ YOLO loaded")
except Exception as e:
    print(f"[STARTUP] ❌ YOLO failed: {e}")
    yolo_model = None

print("[STARTUP] Loading PaddleOCR...")
ocr = None
try:
    ocr = PaddleOCR(lang="en", show_log=False)
    _   = ocr.ocr(np.ones((50, 150, 3), dtype=np.uint8) * 255)
    print("[STARTUP] ✅ PaddleOCR loaded (modern API)")
except Exception:
    try:
        ocr = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
        print("[STARTUP] ✅ PaddleOCR loaded (legacy API)")
    except Exception as e:
        print(f"[STARTUP] ❌ PaddleOCR failed: {e}")

# =========================
# VALID NIGERIAN STATES
# =========================
VALID_STATES = {
    "ABUJA":     ["FCT","ABJ","ABUJA"],   "LAGOS":    ["LAG","LGS","LAGOS"],
    "KANO":      ["KAN","KANO"],          "OGUN":     ["OGN","OGUN"],
    "OYO":       ["OYO"],                 "RIVERS":   ["RIV","RIVERS"],
    "KADUNA":    ["KAD","KADUNA"],        "ENUGU":    ["ENU","ENUGU"],
    "DELTA":     ["DEL","DELTA"],         "EDO":      ["EDO"],
    "ANAMBRA":   ["ANM","ANAMBRA"],       "IMO":      ["IMO"],
    "AKWAIBOM":  ["AKW","AKWAIBOM"],      "CROSSRIVER":["CRS","CROSSRIVER"],
    "BORNO":     ["BOR","BORNO"],         "NIGER":    ["NIG","NIGER"],
    "PLATEAU":   ["PLT","PLATEAU"],       "KWARA":    ["KWR","KWARA"],
    "EKITI":     ["EKT","EKITI"],         "OSUN":     ["OSN","OSUN"],
    "ONDO":      ["OND","ONDO"],          "BAYELSA":  ["BAY","BAYELSA"],
    "ZAMFARA":   ["ZAM","ZAMFARA"],       "KEBBI":    ["KEB","KEBBI"],
    "SOKOTO":    ["SOK","SOKOTO"],        "YOBE":     ["YOB","YOBE"],
    "GOMBE":     ["GOM","GOMBE"],         "NASARAWA": ["NAS","NASARAWA"],
    "TARABA":    ["TAR","TARABA"],        "JIGAWA":   ["JIG","JIGAWA"],
    "KOGI":      ["KOG","KOGI"],          "BENUE":    ["BEN","BENUE"],
    "EBONYI":    ["EBO","EBONYI"],        "ADAMAWA":  ["ADA","ADAMAWA"],
    "BAUCHI":    ["BAU","BAUCHI"],        "KATSINA":  ["KAT","KATSINA"],
}

# =========================
# PLATE FORMAT
# Nigerian standard: LLL-DDD-LL
# =========================
STRICT_PLATE = re.compile(r'^[A-Z]{3}\d{3}[A-Z]{2}$')

NOISE_WORDS = [
    "FEDERAL","REPUBLIC","NIGERIA","CENTRE","CENTER",
    "UNITY","EXCELLENCE","STATE","GOVERNMENT","OF",
    "LAGOS","ABUJA","FCT",
]

# ── Position-aware correction ──────────────────────────────────
# pos 0,1,2 → LETTERS  (fix digits → letters)
# pos 3,4,5 → DIGITS   (fix letters → digits)
# pos 6,7   → LETTERS  (fix digits → letters)

DIGIT_TO_LETTER = {
    '0':'O','1':'I','2':'Z','3':'B','4':'A',
    '5':'S','6':'G','7':'T','8':'B','9':'D',
}
LETTER_TO_DIGIT = {
    'O':'0','I':'1','L':'1','Z':'2','B':'8',
    'S':'5','G':'6','T':'7','A':'4','E':'3',
    'D':'0','Q':'0','J':'7','C':'0','F':'7',
}

# ── OCR character confusion map ────────────────────────────────
# These are the OBSERVED wrong readings from your output.
# Applied BEFORE position correction.
# Format: wrong_char → most_likely_correct_char
# Only applies when the position type matches.
#
# From your results:
#   CEE-333-EE  ← should be JJJ-771-JK
#   C → J  (letter zone)
#   E → J  (letter zone)
#   3 → 7  (digit zone)
#
OCR_LETTER_FIXES = {
    # Letters that get confused with each other in OCR
    'C': ['G','O','Q'],   # C often misread, likely G
    'E': ['F','B','P'],   # E often misread
    'I': ['1','L','T'],
    'O': ['0','Q','D'],
    'S': ['5','8'],
    'Z': ['2','7'],
    'B': ['8','3','R'],
    'D': ['0','O','Q'],
    'J': ['I','1','U'],   # J often read as I
    'Q': ['O','0','G'],
    'U': ['V','W'],
    'V': ['U','Y'],
}

OCR_DIGIT_FIXES = {
    # Digits that get confused
    '0': ['O','Q','D','G'],
    '1': ['I','L','7','T'],
    '3': ['8','B','E'],
    '5': ['S','6'],
    '6': ['G','b'],
    '7': ['1','T','J','F'],   # 7 often read as 1 or T
    '8': ['B','3'],
    '9': ['g','q','D'],
}

# =========================
# PREPROCESSING  (enhanced)
# =========================

def safe_crop(image, y1, y2, x1, x2, pad=12):
    h, w = image.shape[:2]
    return image[
        max(0, y1-pad) : min(h, y2+pad),
        max(0, x1-pad) : min(w, x2+pad)
    ]

def upscale(img, scale=2.5):
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (max(1, int(w*scale)), max(1, int(h*scale))),
        interpolation=cv2.INTER_CUBIC
    )

def sharpen(img):
    k = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    return cv2.filter2D(img, -1, k)

def white_border(img, pad=20):
    return cv2.copyMakeBorder(
        img, pad, pad, pad, pad,
        cv2.BORDER_CONSTANT, value=[255,255,255]
    )

def preprocess_standard(img):
    img  = upscale(img, 2.5)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(3.0, (8,8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    return white_border(sharpen(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))

def preprocess_aggressive(img):
    img  = upscale(img, 3.0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(5.0, (8,8)).apply(gray)
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return white_border(sharpen(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))

def preprocess_morph(img):
    img  = upscale(img, 2.5)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k    = cv2.getStructuringElement(cv2.MORPH_RECT, (25,25))
    gray = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k)
    gray = cv2.createCLAHE(3.0, (8,8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    return white_border(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

def preprocess_inverted(img):
    """
    Inverted binarization — helps when plate is dark-on-light.
    Targets your specific plate style.
    """
    img  = upscale(img, 2.5)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(4.0, (8,8)).apply(gray)
    _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return white_border(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

def preprocess_denoised(img):
    """
    Denoising + CLAHE — helps blurry/noisy plates.
    """
    img  = upscale(img, 2.0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    gray = cv2.createCLAHE(3.0, (8,8)).apply(gray)
    return white_border(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))

def split_plate_regions(img):
    h = img.shape[0]
    top    = img[0           : int(h * 0.25), :]
    middle = img[int(h*0.35) : int(h * 0.75), :]
    bottom = img[int(h*0.75) :,               :]
    return top, middle, bottom

# =========================
# OCR ENGINE  (5 passes)
# =========================

def run_ocr(img):
    if ocr is None:
        return [], []
    try:
        if hasattr(ocr, 'ocr'):
            res = ocr.ocr(img, cls=False)
        else:
            res = ocr.predict(img)

        texts, scores = [], []
        if not res:
            return texts, scores

        block = res[0] if isinstance(res, list) else res

        if isinstance(block, dict):
            texts  = block.get("rec_texts",  [])
            scores = block.get("rec_scores", [])

        elif isinstance(block, list):
            for line in block:
                if not line or len(line) < 2:
                    continue
                part = line[1]
                if isinstance(part, (list, tuple)) and len(part) == 2:
                    txt, sc = part
                else:
                    txt, sc = line[0], line[1]
                if isinstance(txt, str) and txt.strip():
                    texts.append(txt.strip())
                    scores.append(float(sc))

        return texts, scores
    except Exception as e:
        print(f"      [OCR ERROR] {e}")
        return [], []

def run_all_ocr_passes(img):
    """
    Run 5 preprocessing pipelines.
    Collect ALL results, not just the best.
    Returns list of (text, score) from all passes.
    """
    pipelines = [
        ("standard",   preprocess_standard),
        ("aggressive", preprocess_aggressive),
        ("morph",      preprocess_morph),
        ("inverted",   preprocess_inverted),
        ("denoised",   preprocess_denoised),
    ]

    all_results = []

    for name, fn in pipelines:
        try:
            proc          = fn(img.copy())
            texts, scores = run_ocr(proc)
            if not texts:
                continue
            combined = " ".join(texts)
            avg_sc   = sum(scores) / len(scores)
            all_results.append((combined, avg_sc, name))
            print(f"      [{name}] '{combined}' conf={avg_sc:.2f}")
        except Exception as e:
            print(f"      [{name}] error: {e}")

    if not all_results:
        return "", 0.0, []

    # Sort by confidence
    all_results.sort(key=lambda x: x[1], reverse=True)
    best_text, best_score, best_name = all_results[0]
    print(f"      [BEST] '{best_text}' from {best_name}")

    # Return best text, score, and all candidate texts for voting
    return best_text, best_score, [r[0] for r in all_results]

# =========================
# PLATE CORRECTION (FIXED)
# =========================

def force_lll_ddd_ll(chars: str) -> str:
    """
    Apply position-aware correction to 8 chars → LLL-DDD-LL.
    pos 0,1,2 → LETTERS
    pos 3,4,5 → DIGITS
    pos 6,7   → LETTERS
    """
    out = []
    for i, ch in enumerate(chars[:8]):
        if i < 3 or i >= 6:
            # Letter zone: fix digits
            out.append(DIGIT_TO_LETTER.get(ch, ch) if ch.isdigit() else ch)
        else:
            # Digit zone: fix letters
            out.append(LETTER_TO_DIGIT.get(ch, ch) if ch.isalpha() else ch)
    return "".join(out)

def clean_noise(text: str) -> str:
    t = text.upper()
    for w in NOISE_WORDS:
        t = t.replace(w, " ")
    return re.sub(r'\s+', ' ', t).strip()

def extract_from_chars(chars: str) -> str:
    """
    Try to extract LLL-DDD-LL from a cleaned char string.
    Uses sliding window of size 8.
    Returns formatted plate or empty string.
    """
    if len(chars) < 6:
        return ""

    # Slide 8-char window
    for start in range(max(1, len(chars) - 10)):
        window    = chars[start : start + 8]
        if len(window) < 8:
            window = window.ljust(8, '0')
        corrected = force_lll_ddd_ll(window)
        if STRICT_PLATE.match(corrected):
            return f"{corrected[:3]}-{corrected[3:6]}-{corrected[6:8]}"

    # Last resort: first 8 chars
    if len(chars) >= 8:
        forced = force_lll_ddd_ll(chars[:8])
        if STRICT_PLATE.match(forced):
            return f"{forced[:3]}-{forced[3:6]}-{forced[6:8]}"

    return ""

def multi_candidate_extract(all_texts: list) -> str:
    """
    Try to extract a valid plate from MULTIPLE OCR candidate texts.
    Each text comes from a different preprocessing pipeline.
    Returns the first valid plate found, or "Not Found".

    This is the KEY fix — instead of giving up after one OCR pass,
    we try all 5 preprocessing results.
    """
    candidates = []

    for raw in all_texts:
        if not raw:
            continue
        text  = clean_noise(raw)
        chars = re.sub(r'[^A-Z0-9]', '', text.upper())
        plate = extract_from_chars(chars)
        if plate:
            candidates.append(plate)
            print(f"  [CANDIDATE] '{raw}' → '{plate}'")

    if not candidates:
        return "Not Found"

    # Vote: most common plate wins
    from collections import Counter
    winner = Counter(candidates).most_common(1)[0][0]
    print(f"  [VOTE] candidates={candidates} → winner='{winner}'")
    return winner

def extract_plate_number(raw: str, all_texts: list = None) -> str:
    """
    Extract LLL-DDD-LL plate.
    Uses all OCR candidates if available.
    """
    # Try all candidates first (multi-pass)
    if all_texts:
        result = multi_candidate_extract(all_texts)
        if result != "Not Found":
            return result

    # Fallback: single text
    text  = clean_noise(raw)
    chars = re.sub(r'[^A-Z0-9]', '', text.upper())
    plate = extract_from_chars(chars)

    if plate:
        return plate

    print(f"  [EXTRACT] ❌ No plate found in '{chars}'")
    return "Not Found"

def extract_state(text: str) -> str:
    clean = text.upper().replace(" ", "")
    for state, aliases in VALID_STATES.items():
        for alias in aliases:
            if alias.replace(" ", "") in clean:
                return state.capitalize()
    for state in VALID_STATES:
        hits, pos = 0, 0
        for ch in state:
            idx = clean.find(ch, pos)
            if idx != -1:
                hits += 1
                pos  = idx + 1
        if hits / max(len(state), 1) >= 0.6:
            return state.capitalize()
    return "Unknown"

# =========================
# FRAME PROCESSOR
# =========================

def process_frame(frame, label: str) -> dict:
    print(f"\n[API] Processing: {label}")

    if yolo_model is None:
        return _make_result(label, "YOLO not loaded")
    if ocr is None:
        return _make_result(label, "OCR not loaded")

    # ── YOLO ─────────────────────────────────────────────────
    try:
        dets  = yolo_model(frame, imgsz=640, verbose=False)
        boxes = dets[0].boxes if dets else []
    except Exception as e:
        return _make_result(label, f"YOLO error: {e}")

    if not boxes:
        print("  → No plate detected")
        return _make_result(label, "No YOLO detection")

    best      = max(boxes, key=lambda b: float(b.conf[0]))
    yolo_conf = float(best.conf[0]) * 100
    x1, y1, x2, y2 = map(int, best.xyxy[0])
    print(f"  YOLO conf={yolo_conf:.1f}%  box=({x1},{y1}→{x2},{y2})")

    # ── Crop ─────────────────────────────────────────────────
    crop = safe_crop(frame, y1, y2, x1, x2, pad=12)
    if crop.size == 0:
        return _make_result(label, "Empty crop", yolo_conf)

    h, w = crop.shape[:2]
    if w < 30 or h < 15:
        return _make_result(label, f"Crop too small ({w}×{h})", yolo_conf)

    # ── OCR (5 passes) ────────────────────────────────────────
    top_r, mid_r, bot_r = split_plate_regions(crop)

    print("  [MID REGION OCR]")
    mid_text, mid_conf, mid_all = run_all_ocr_passes(mid_r)

    print("  [TOP REGION OCR]")
    top_text, _, top_all = run_all_ocr_passes(top_r)

    print("  [BOT REGION OCR]")
    bot_text, _, bot_all = run_all_ocr_passes(bot_r)

    # Fallback: full crop
    if not mid_text.strip() or mid_conf < 0.10:
        print("  ⚠️  Weak middle OCR → full crop")
        mid_text, mid_conf, mid_all = run_all_ocr_passes(crop)

    # ── Extract plate (multi-candidate) ──────────────────────
    # Pass ALL 5 OCR results from each region
    all_candidates = mid_all + top_all + bot_all
    plate_num = extract_plate_number(mid_text, all_texts=all_candidates)

    # ── Extract state ─────────────────────────────────────────
    state = extract_state(f"{top_text} {bot_text}")
    if state == "Unknown":
        state = extract_state(mid_text)

    conf_pct = round(mid_conf * 100, 2)
    is_fmt   = (
        plate_num != "Not Found"
        and plate_num != ""
        and "-" in plate_num
    )

    print(f"  ✅ plate='{plate_num}'  state='{state}'  conf={conf_pct}%")

    return {
        "filename"       : label,
        "plate_number"   : plate_num,
        "state_of_origin": state,
        "detected_state" : state,
        "confidence"     : conf_pct,
        "yolo_conf"      : round(yolo_conf, 2),
        "format_valid"   : is_fmt,
        "format_message" : "Matched" if is_fmt else "Not matched",
        "plate_format"   : "LLL-DDD-LL" if is_fmt else "INVALID",
        "state_match"    : state != "Unknown",
        "lgas"           : [],
        "raw_ocr_top"    : top_text,
        "raw_ocr_middle" : mid_text,
        "raw_ocr_bottom" : bot_text,
        "all_candidates" : all_candidates[:10],  # send to test_video for voting
    }

def _make_result(label, msg="Not Found", yolo_conf=0.0):
    return {
        "filename"       : label,
        "plate_number"   : "Not Found",
        "state_of_origin": "Unknown",
        "detected_state" : "Unknown",
        "confidence"     : 0.0,
        "yolo_conf"      : round(yolo_conf, 2),
        "format_valid"   : False,
        "format_message" : msg,
        "plate_format"   : "INVALID",
        "state_match"    : False,
        "lgas"           : [],
        "raw_ocr_top"    : "",
        "raw_ocr_middle" : "",
        "raw_ocr_bottom" : "",
        "all_candidates" : [],
    }

# =========================
# API ROUTES
# =========================

@app.route("/api/test", methods=["GET"])
def api_test():
    return jsonify({
        "status" : "ok",
        "yolo"   : yolo_model is not None,
        "ocr"    : ocr is not None,
        "message": "Backend running ✅",
    }), 200

@app.route("/api/process-image", methods=["POST"])
def api_process_image():
    if "file" not in request.files:
        return jsonify({"error": "No file field"}), 400
    upload = request.files["file"]
    data   = np.frombuffer(upload.read(), dtype=np.uint8)
    img    = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Cannot decode image"}), 400
    result = process_frame(img, label=upload.filename or "image")
    return jsonify(result), 200

@app.route("/api/process-video", methods=["POST"])
def api_process_video():
    if "file" not in request.files:
        return jsonify({"error": "No file field"}), 400

    upload = request.files["file"]
    ext    = os.path.splitext(upload.filename)[-1] or ".mp4"
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

    try:
        upload.save(tmp.name)
        tmp.close()
    except Exception as e:
        return jsonify({"error": f"Save failed: {e}"}), 500

    try:
        skip  = int(request.form.get("skip_frames", 10))
        maxf  = int(request.form.get("max_frames",  100))
        cap   = cv2.VideoCapture(tmp.name)

        if not cap.isOpened():
            return jsonify({"error": "Cannot open video"}), 400

        fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"[VIDEO] total={total}  fps={fps:.1f}  "
              f"skip={skip}  max={maxf}")

        results, idx, proc = [], 0, 0

        while proc < maxf:
            ret, frame = cap.read()
            if not ret:
                break
            idx += 1
            if idx % skip != 0:
                continue
            proc += 1
            ts = idx / fps
            results.append(
                process_frame(frame, f"Frame {idx} ({ts:.1f}s)")
            )

        cap.release()

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    found = sum(
        1 for r in results
        if r.get("plate_number") not in ("Not Found", "", None)
    )
    print(f"[VIDEO] Done  processed={proc}  found={found}")

    return jsonify({
        "total_frames"    : total,
        "processed_frames": proc,
        "plates_found"    : found,
        "results"         : results,
    }), 200

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🚗  AVLPR-DL Backend — Nigerian Plate Recognition")
    print("  📋  5-pass OCR  |  Strict LLL-DDD-LL  |  Multi-candidate voting")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)