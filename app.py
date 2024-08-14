from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import base64
import numpy as np
import cv2
import torch
import openai
from google.cloud import speech, texttospeech
from dotenv import load_dotenv
import os

# Initialize Flask app
load_dotenv()
app = Flask(__name__) 

CORS(app)  # Enable Cross-Origin Resource Sharing

# Load YOLOv5 model
yolo_model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

openai.api_key = os.getenv('OPENAI_API_KEY')
# Initialize Google Cloud clients
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

def detect_walls(frame, mask=None):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if mask is not None:
        gray = cv2.bitwise_and(gray, gray, mask=mask)
    edges = cv2.Canny(gray, 50, 150)
    dilated = cv2.dilate(edges, None, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    walls = []
    frame_center = frame.shape[1] // 2
    for contour in contours:
        if cv2.contourArea(contour) > 1000:
            x, y, w, h = cv2.boundingRect(contour)
            if abs(x + w // 2 - frame_center) < frame.shape[1] // 4:
                constant = 2000
                estimated_distance = constant / w
                if estimated_distance < 20:
                    walls.append((x, y, w, h))
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                    cv2.putText(frame, f'Wall {estimated_distance:.2f}', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    return walls

def draw_detections(frame, detections):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    for _, row in detections.iterrows():
        xmin, ymin, xmax, ymax, label, confidence = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax']), row['name'], row['confidence']
        if label == 'person':
            mask[ymin:ymax, xmin:xmax] = 255
        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        cv2.putText(frame, f'{label} {confidence:.2f}', (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    return mask

def generate_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        try:
            results = yolo_model(frame)
            detections = results.pandas().xyxy[0]
            mask = draw_detections(frame, detections)

            walls = detect_walls(frame, mask)

            close_wall = any(wall[2] > frame.shape[1] // 2 for wall in walls)
            close_object = any((row['xmax'] - row['xmin']) > frame.shape[1] // 2 for _, row in detections.iterrows())
            
            if close_wall or close_object:
                action_text = "Stop & Turn Right"
            else:
                action_text = "Move Forward"
            
            cv2.putText(frame, action_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print(f"Action: {action_text}")
        except Exception as e:
            print(f"Error: {e}")

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return send_from_directory('static', 'chat.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        file = request.files['audio']
        audio = speech.RecognitionAudio(content=file.read())
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            language_code='ko-KR'  
        )

        response = speech_client.recognize(config=config, audio=audio)
        transcript = " ".join([result.alternatives[0].transcript for result in response.results])
        return jsonify({'text': transcript})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_message = data.get('text')

    try:
        # OpenAI API를 사용하여 응답 생성 (최신 인터페이스에 맞게 수정)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}]
        )
        response_message = response.choices[0].message['content']

        # TTS 응답 생성
        synthesis_input = texttospeech.SynthesisInput(text=response_message)
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,  # MP3 대신 LINEAR16 사용
    speaking_rate=1.0,
    pitch=5
)

        tts_response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        audio_content = tts_response.audio_content
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')

        return jsonify({'message': response_message, 'audio_base64': audio_base64})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_frame', methods=['POST'])
def analyze_frame():
    try:
        data = request.get_json()
        encoded_data = data['image'].split(',')[1]
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Implement age detection here
        # Replace with actual implementation or library call
        age = 30  # Placeholder value
        return jsonify({'age': age})
    except Exception as e:
        app.logger.error(f"Error in /analyze_frame: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    cert_path = os.path.join(os.path.dirname(__file__), 'server.crt')
    key_path = os.path.join(os.path.dirname(__file__), 'server.key')
    app.run(
        host='0.0.0.0',
        port=5000,
        ssl_context=(cert_path, key_path),  # 절대 경로 사용
        debug=True
    )