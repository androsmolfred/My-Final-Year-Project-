# test_app.py
import requests
import os
import time
import json
from datetime import datetime

# =========================
# CONFIG
# =========================

BASE_URL     = "https://humble-palm-tree-gvj6vgvgg4j3pv6p-5000.app.github.dev/"
IMAGE_FOLDER = "/workspaces/AVLPR-DL/test_images/"
LOG_FILE     = "image_plate_log.txt"

# =========================
# LOGGER
# =========================

def log_result(entry: dict):
    """Append detection result to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = (
        f"\n[{timestamp}]\n"
        f"  Image         : {entry.get('image', 'N/A')}\n"
        f"  Plate Number  : {entry.get('plate_number', 'N/A')}\n"
        f"  State         : {entry.get('state_of_origin', 'N/A')}\n"
        f"  Confidence    : {entry.get('confidence', 'N/A')}%\n"
        f"  {'─'*40}"
    )
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# =========================
# SINGLE IMAGE TEST
# =========================

def test_plate(image_path, base_url):
    """Test a single image and print result cleanly."""

    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return None

    size_mb = os.path.getsize(image_path) / (1024 * 1024)
    print(f"\n📸 {os.path.basename(image_path)}  ({size_mb:.2f} MB)")
    print("   ⏳ Processing...")
    start = time.time()

    try:
        with open(image_path, "rb") as f:
            response = requests.post(
                f"{base_url}/api/process-image",
                files={"file": f},
                timeout=180
            )
    except requests.exceptions.ReadTimeout:
        print("   ❌ Timed out")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

    elapsed = time.time() - start

    if response.status_code != 200:
        print(f"   ❌ Server error: {response.status_code}")
        return None

    if not response.text.strip():
        print("   ❌ Empty response")
        return None

    try:
        result = response.json()
    except Exception:
        print("   ❌ Could not parse JSON")
        return None

    # ── FIX: Handle both flat dict and {"results": [...]} formats ──
    if isinstance(result, dict) and "plate_number" in result:
        plates = [result]  # Wrap flat dict in list
    else:
        plates = result.get("results", [])

    if not plates:
        print(f"   ⚠️  No plates detected ({elapsed:.1f}s)")
        return None

    # Take the first detected plate
    plate = plates[0]
    plate_num   = plate.get("plate_number", "Not Found")
    state       = plate.get("state_of_origin", "Unknown")
    confidence  = plate.get("confidence", 0)

    # Clean terminal output
    print(f"   ✅ Plate : {plate_num}")
    print(f"   📍 State : {state}")
    print(f"   📊 Conf  : {confidence}%")
    print(f"   ⏱️  Time  : {elapsed:.1f}s")

    # Log full details
    log_result({
        "image"         : os.path.basename(image_path),
        "plate_number"  : plate_num,
        "state_of_origin": state,
        "confidence"    : confidence,
    })

    return plate

# =========================
# BATCH TEST
# =========================

def test_all_images(image_folder, base_url):
    """Test all images in a folder."""

    if not os.path.exists(image_folder):
        print(f"❌ Folder not found: {image_folder}")
        return

    images = sorted([
        f for f in os.listdir(image_folder)
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif'))
    ])

    if not images:
        print(f"❌ No images found in {image_folder}")
        return

    # Check backend
    try:
        r = requests.get(f"{base_url}/api/test", timeout=10)
        if r.status_code == 200:
            print("✅ Backend is running\n")
        else:
            print("⚠️  Backend may be unhealthy")
    except Exception:
        print("❌ Backend not running. In Terminal 1 run: python main.py")
        return

    print(f"📁 Folder : {image_folder}")
    print(f"📸 Images : {len(images)}")
    print("=" * 50)

    total_start   = time.time()
    detected      = 0
    not_detected  = 0

    for idx, img_name in enumerate(images, 1):
        image_path = os.path.join(image_folder, img_name)
        result = test_plate(image_path, base_url)
        if result:
            detected += 1
        else:
            not_detected += 1

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"  Total Images    : {len(images)}")
    print(f"  Plates Detected : {detected}")
    print(f"  No Detection    : {not_detected}")
    print(f"  Total Time      : {total_elapsed:.1f}s")
    print(f"  Avg Time/Image  : {total_elapsed/len(images):.1f}s")
    print(f"  Log File        : {LOG_FILE}")
    print("=" * 50)

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    test_all_images(IMAGE_FOLDER, BASE_URL)