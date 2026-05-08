import os
import cv2
from google.cloud import vision

# 1. AUTHENTICATION: This tells Google exactly where your secret key is
# It uses absolute paths so it never gets lost, just like our test_api.py script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "google_secret.json")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

def test_google_ocr(image_filename):
    # Get the absolute path to the image
    image_path = os.path.join(BASE_DIR, image_filename)
    
    print(f"\n[GOOGLE API] Connecting to Cloud Vision...")
    print(f"[GOOGLE API] Looking for image at: {image_path}")
    
    # Check if image exists
    if not os.path.exists(image_path):
        print(f"\n[ERROR] Could not find '{image_filename}'!")
        print("Please make sure it is in the same folder as this script.")
        return

    # 2. LOAD IMAGE WITH OPENCV
    print("[GOOGLE API] Loading image into memory...")
    frame = cv2.imread(image_path)
    if frame is None:
        print("\n[ERROR] OpenCV failed to load the image. Is the file corrupted?")
        return

    # 3. PREPARE IMAGE FOR GOOGLE
    # Google requires bytes over the internet, not a massive numpy array
    print("[GOOGLE API] Encoding image for internet transfer...")
    success, encoded_image = cv2.imencode('.jpg', frame)
    if not success:
        print("\n[ERROR] Failed to encode image to .jpg format.")
        return
        
    content = encoded_image.tobytes()
    image = vision.Image(content=content)

    # 4. SEND TO GOOGLE
    print("[GOOGLE API] Sending to Google Cloud supercomputers...")
    try:
        client = vision.ImageAnnotatorClient()
        # We specifically ask for text detection
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        # Check for Google-side errors (like billing or API not enabled)
        if response.error.message:
            raise Exception(f"{response.error.message}")

        if texts:
            # texts[0].description contains the entire block of text Google found
            # We replace newlines with spaces so it prints cleanly on one line
            found_text = texts[0].description.replace('\n', ' ')
            print(f"\n======================================")
            print(f" [SUCCESS] Google Found:  {found_text} ")
            print(f"======================================")
        else:
            print("\n[RESULT] Google processed the image but did not find any text.")

    except Exception as e:
        print(f"\n[CRASH] Google API Error: {e}")
        print("Did you remember to enable the Cloud Vision API in the Google Console?")

if __name__ == "__main__":
    # Test it on your specific Nigerian car image
    test_google_ocr("NigCar_11.png")