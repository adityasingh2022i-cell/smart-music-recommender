import cv2
from deepface import DeepFace

def detect_mood():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cv2.imshow("Capturing Mood", frame)
    cv2.waitKey(2000)
    cap.release()
    cv2.destroyAllWindows()

    try:
        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        mood = result[0]['dominant_emotion']
        return mood
    except Exception as e:
        print("Error detecting mood:", e)
        return "neutral"
