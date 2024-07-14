let mediaRecorder;
let audioChunks = [];
let isActive = false; // 녹음 활성화 상태 표시
let detectedAge = 0; // 감지된 나이 저장
let interactionTimeout; // 상호작용 타이머

window.onload = function() {
    navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
        setInterval(() => captureFrame(stream), 10000); //나이 감지 : 10초
    }).catch(err => console.error("Failed to access video device", err));

    resetInteractionTimeout(); // 페이지 로드 시 타이머 시작
};
function toggleRecording() {
    if (!isActive) {
        startRecording();
        document.getElementById("toggleBtn").textContent = "녹음 종료";
        clearTimeout(interactionTimeout); // 녹음 시작 시 타이머 중지
    } else {
        stopRecording();
        document.getElementById("toggleBtn").textContent = "녹음 시작";
        // 녹음 종료 후 타이머 재설정은 녹음 종료와 응답 처리가 모두 완료된 후에 실행
    }
    isActive = !isActive;
}

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then((audioStream) => {
            mediaRecorder = new MediaRecorder(audioStream, { mimeType: "audio/webm" });
            mediaRecorder.start();
            mediaRecorder.ondataavailable = function (e) {
                audioChunks.push(e.data);
            };
            mediaRecorder.onstop = sendAudioToServer;
        })
        .catch((err) => console.error("Failed to access audio devices", err));
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
}

function sendAudioToServer() {
    if (audioChunks.length > 0) {
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        audioChunks = [];
        const formData = new FormData();
        formData.append("audio", audioBlob);

        fetch("http://127.0.0.1:5000/transcribe", {
            method: "POST",
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById("transcript").textContent = "질문: " + data.text;
            return fetch("http://127.0.0.1:5000/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: data.text }),
            });
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById("response").textContent = data.message;
            speak(data.message);
        })
        .catch(error => console.error("Error:", error));
    }
}

function speak(message) {
    const speech = new SpeechSynthesisUtterance(message);
    speech.lang = "ko-KR";
    speech.pitch = 1;
    speech.rate = detectedAge >= 65 ? 0.8 : 1;
    document.getElementById("response").style.fontSize = detectedAge >= 65 ? "4em" : "2em";
    window.speechSynthesis.speak(speech);
    speech.onend = () => {
        document.getElementById("toggleBtn").disabled = false;
        resetInteractionTimeout(); // TTS 종료 후 타이머 재설정
    };
}

function resetInteractionTimeout() {
    clearTimeout(interactionTimeout);
    interactionTimeout = setTimeout(function () {
        window.location.href = "robot.html";
    }, 5000);
}

// 나이 측정 및 화면 출력 로직이 포함된 captureFrame 함수
function captureFrame(stream) {
    const video = document.createElement('video');
    video.srcObject = stream;
    const canvas = document.createElement('canvas');
    canvas.width = 640; // 비디오와 동일한 해상도 설정
    canvas.height = 480;
    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL('image/png');

    fetch('http://127.0.0.1:5000/analyze_frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: data })
    })
    .then(response => response.json())
    .then(data => {
        detectedAge = data.age;
        document.getElementById('age').textContent = 'Detected Age: ' + detectedAge;
    })
    .catch(error => console.error('Error in age detection:', error));
}
