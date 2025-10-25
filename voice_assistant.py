import os
import json
from flask import Flask, send_from_directory
from flask_sock import Sock
import requests
import asyncio
import websockets
import threading

# -------------------
# 配置
# -------------------
GEMINI_API_KEY = os.environ.get("AIzaSyAP48FPp9uqmlHoZz4nYJt31byMjxV7fjE")
MODEL = "models/gemini-2.5-flash-native-audio-preview-09-2025"
GEMINI_URL = f"wss://generativelanguage.googleapis.com/v1beta/{MODEL}:streamGenerateContent?key={GEMINI_API_KEY}"

app = Flask(__name__)
sock = Sock(app)

# -------------------
# 前端网页 (直接内嵌)
# -------------------
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Gemini Live Web Full Demo</title>
  <style>
    body { font-family: sans-serif; }
    video { width: 320px; border: 1px solid #ccc; }
    #log { white-space: pre-wrap; background: #f5f5f5; padding: 10px; height: 200px; overflow-y: auto; }
  </style>
</head>
<body>
  <h2>🎤 Gemini Live Web Full Demo</h2>
  <video id="camera" autoplay playsinline></video><br>
  <button id="startBtn">Start</button>
  <button id="stopBtn">Stop</button>
  <input id="textInput" placeholder="Type message..." />
  <button id="sendText">Send</button>
  <div id="log"></div>

  <script>
    let ws, mediaStream, mediaRecorder, audioCtx;

    function log(msg) {
      document.getElementById("log").textContent += msg + "\\n";
    }

    async function startSession() {
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        document.getElementById("camera").srcObject = mediaStream;

        ws = new WebSocket("ws://" + window.location.host + "/live");

        ws.onopen = () => log("✅ Connected to proxy");
        ws.onmessage = async (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.text) log("Gemini: " + msg.text);
            if (msg.data && msg.mime_type && msg.mime_type.startsWith("audio")) {
              playAudio(msg.data);
            }
          } catch {
            log("Raw: " + event.data);
          }
        };

        // 添加MIME类型检测
        let options = { mimeType: 'audio/webm' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          console.error('audio/webm not supported, trying audio/webm;codecs=opus');
          options = { mimeType: 'audio/webm;codecs=opus' };
          if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            console.error('audio/webm;codecs=opus not supported, using default');
            options = {};
          }
        }

        mediaRecorder = new MediaRecorder(mediaStream, options);
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            e.data.arrayBuffer().then(buf => {
              ws.send(buf);
            });
          }
        };
        mediaRecorder.start(250);

        const video = document.getElementById("camera");
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");
        setInterval(() => {
          if (video.videoWidth === 0) return;
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          ctx.drawImage(video, 0, 0);
          canvas.toBlob(blob => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then(buf => {
                ws.send(buf);
              });
            }
          }, "image/jpeg");
        }, 1000);
      } catch (err) {
        console.error('Error in startSession:', err);
        log('❌ Error: ' + err.message);
      }
    }

    function stopSession() {
      if (mediaRecorder) mediaRecorder.stop();
      if (ws) ws.close();
      if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
      log("🛑 Session stopped");
    }

    function sendText() {
      const text = document.getElementById("textInput").value;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ input: text, end_of_turn: true }));
        log("You: " + text);
      }
    }

    function playAudio(base64Data) {
      if (!audioCtx) audioCtx = new AudioContext();
      const byteArray = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));
      audioCtx.decodeAudioData(byteArray.buffer, (buffer) => {
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(audioCtx.destination);
        source.start();
      });
    }

    document.getElementById("startBtn").onclick = startSession;
    document.getElementById("stopBtn").onclick = stopSession;
    document.getElementById("sendText").onclick = sendText;
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_PAGE

@app.route('/favicon.ico')
def favicon():
    return '', 204

# -------------------
# WebSocket 代理
# -------------------
@sock.route('/live')
def live(ws):
    async def proxy():
        # 移除Authorization头，因为API key已在URL中
        async with websockets.connect(GEMINI_URL) as gemini:
            async def ws_to_gemini():
                while True:
                    msg = await asyncio.to_thread(ws.receive)
                    if msg is None:
                        break
                    await gemini.send(msg)

            async def gemini_to_ws():
                async for msg in gemini:
                    ws.send(msg)

            await asyncio.gather(ws_to_gemini(), gemini_to_ws())

    asyncio.run(proxy())

# -------------------
# 启动
# -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
