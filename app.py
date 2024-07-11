from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
import os
from openai import OpenAI
from google.cloud import speech, texttospeech
from flask_cors import CORS
import base64
import cv2
from deepface import DeepFace
import numpy as np


load_dotenv()  
app = Flask(__name__)
CORS(app)  


api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)


os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()

def generate_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            try:
                result = DeepFace.analyze(frame, actions=['age'], enforce_detection=False)
                age = result['age']
                cv2.putText(frame, f'Age: {age}', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            except Exception as e:
                pass

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_message}]
        )
        response_message = completion.choices[0].message.content

        synthesis_input = texttospeech.SynthesisInput(text=response_message)
        voice = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,  # 말하는 속도 조정
            pitch=5  # 말투의 피치 조정
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

        result = DeepFace.analyze(img, actions=['age'], enforce_detection=False)

        age = result[0]['age'] if isinstance(result, list) else result['age']
        return jsonify({'age': age})
    except Exception as e:
        app.logger.error(f"Error in /analyze_frame: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
