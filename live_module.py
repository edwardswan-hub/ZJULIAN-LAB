import asyncio
import json
import os
import sys
from google import genai
from google.genai import types
import pyaudio
import numpy as np
import threading
import queue
import wave
import tempfile

# 音频配置
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5

class AudioRecorder:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.recording = False
        self.frames = []
        self.audio_queue = queue.Queue()
        
    def start_recording(self):
        self.frames = []
        self.stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                    rate=RATE, input=True,
                                    frames_per_buffer=CHUNK)
        self.recording = True
        
        def record():
            while self.recording:
                data = self.stream.read(CHUNK)
                self.frames.append(data)
                self.audio_queue.put(data)
        
        self.thread = threading.Thread(target=record)
        self.thread.start()
    
    def stop_recording(self):
        self.recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'thread'):
            self.thread.join()
    
    def get_audio_data(self):
        return b''.join(self.frames)
    
    def cleanup(self):
        self.audio.terminate()

class AudioPlayer:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
    def play_audio(self, audio_data):
        self.stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                    rate=RATE, output=True)
        self.stream.write(audio_data)
        self.stream.stop_stream()
        self.stream.close()
    
    def cleanup(self):
        self.audio.terminate()

class GeminiLiveSession:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            generation_config=types.GenerationConfig(
                response_modalities=["AUDIO"],
                candidate_count=1,
                max_output_tokens=1024,
                temperature=0.7,
            ),
        )
        self.recorder = AudioRecorder()
        self.player = AudioPlayer()
        self.session = None
        self.running = False
        
    async def start_session(self):
        try:
            self.session = await self.client.aio.live.connect(model="gemini-2.0-flash-exp", config=self.config)
            self.running = True
            
            # 启动音频处理任务
            asyncio.create_task(self.process_audio())
            asyncio.create_task(self.receive_audio())
            
            print("Gemini Live会话已启动")
            
            # 发送初始消息
            await self.session.send(types.LiveClientMessage(
                content=[{"text": "你好，我是你的AI助手，请开始说话。"}],
            ))
            
        except Exception as e:
            print(f"启动会话失败: {e}")
            self.running = False
    
    async def process_audio(self):
        while self.running:
            try:
                # 从队列获取音频数据
                audio_data = self.recorder.audio_queue.get()
                
                # 发送音频到Gemini
                await self.session.send(types.LiveClientMessage(
                    realtime_input=types.RealtimeInput(
                        media_chunks=[types.Blob(
                            mime_type="audio/pcm",
                            data=audio_data,
                        )],
                    ),
                ))
                
            except Exception as e:
                print(f"处理音频错误: {e}")
                await asyncio.sleep(0.1)
    
    async def receive_audio(self):
        while self.running:
            try:
                # 接收Gemini的响应
                async for response in self.session.receive():
                    if response.data and response.data.parts:
                        for part in response.data.parts:
                            if part.inline_data and part.inline_data.mime_type == "audio/pcm":
                                # 播放音频
                                self.player.play_audio(part.inline_data.data)
                                
            except Exception as e:
                print(f"接收音频错误: {e}")
                await asyncio.sleep(0.1)
    
    async def run(self):
        await self.start_session()
        
        # 开始录音
        self.recorder.start_recording()
        
        try:
            # 保持会话运行
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("用户中断会话")
        finally:
            await self.stop_session()
    
    async def stop_session(self):
        self.running = False
        self.recorder.stop_recording()
        self.recorder.cleanup()
        self.player.cleanup()
        
        if self.session:
            await self.session.close()
        
        print("Gemini Live会话已结束")

def main_run_loop(api_key):
    """主运行循环，由Flask应用调用"""
    if not api_key:
        print("错误: 未提供Gemini API密钥")
        return
    
    # 设置事件循环策略（Windows需要）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 创建并运行会话
        session = GeminiLiveSession(api_key)
        loop.run_until_complete(session.run())
    except Exception as e:
        print(f"运行会话时出错: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    # 独立运行时的代码
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("请设置GEMINI_API_KEY环境变量")
        sys.exit(1)
    
    main_run_loop(api_key)
