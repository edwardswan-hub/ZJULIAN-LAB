import os
import json
import threading
import re
import time
import shutil
from datetime import datetime
from http import HTTPStatus
from flask import Flask, request, jsonify, Response
import requests
import pandas as pd

# ==============================================================================
# --- 配置 (CONFIG) ---
# ==============================================================================

# --- 目录和文件路径 ---
UPLOAD_DIR = "uploads"
HUB_DATA_FILE = "hub_data.json"
CHAT_LOG_FILE = "chat_log.json"
CACHE_JSON = "movies.json"
SOURCE_EXCEL_NAME = "source.xlsx"

# --- 外部 API 配置 ---
AI_API_URL = "https://jarvisai.deno.dev/v1/chat/completions"
AI_API_KEY = os.environ.get("AI_API_KEY", " ")
AI_MODEL_NAME = "gemini-pro"
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", " ")
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# --- Flask 应用实例 ---
app = Flask(__name__)
file_lock = threading.Lock()

# ==============================================================================
# --- HTML 内容 (EMBEDDED) ---
# ==============================================================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZJULIAN - The Definitive Hub</title>
    <link rel="icon" href="/favicon.ico" type="image/x-icon">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root { --border-radius-lg: 24px; --transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1); }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; color: #f5f5f7; background-color: #000; background-image: url('https://cdn.pixabay.com/photo/2022/05/16/01/15/road-7199274_1280.jpg'); background-size: cover; background-position: center; background-attachment: fixed; min-height: 100vh; overflow-x: hidden; }
        .glass-pane { background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.55); -webkit-backdrop-filter: blur(30px); backdrop-filter: blur(30px); border-radius: var(--border-radius-lg); border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 16px 48px 0 rgba(0, 0, 0, 0.35); }
        
        /* Central Activator */
        #ui-activator { position: fixed; top: 50%; left: 50%; width: 80px; height: 80px; transform: translate(-50%, -50%); border-radius: 50%; cursor: pointer; z-index: 1001; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(30, 30, 30, 0.7); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; opacity: 1; transition: opacity 0.5s ease, transform 0.5s ease; animation: pulse 3s infinite; }
        #ui-activator:hover { transform: translate(-50%, -50%) scale(1.1); animation-play-state: paused; }
        #ui-activator.hidden { opacity: 0; pointer-events: none; }
        @keyframes pulse { 0%, 100% { box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 0 rgba(255,255,255,0.2); } 50% { box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 10px rgba(255,255,255,0); } }
        
        /* Navigation Buttons */
        #nav-buttons { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.5s ease; max-width: 300px; }
        #nav-buttons.active { opacity: 1; pointer-events: all; }
        .nav-button { width: 120px; height: 120px; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.7); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; cursor: pointer; transition: all 0.3s ease; opacity: 0; transform: scale(0.8); }
        #nav-buttons.active .nav-button { opacity: 1; transform: scale(1); }
        #nav-buttons.active .nav-button:nth-child(1) { transition-delay: 0.1s; }
        #nav-buttons.active .nav-button:nth-child(2) { transition-delay: 0.2s; }
        #nav-buttons.active .nav-button:nth-child(3) { transition-delay: 0.3s; }
        #nav-buttons.active .nav-button:nth-child(4) { transition-delay: 0.4s; }
        .nav-button:hover { transform: scale(1.05); background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.8); }
        .nav-button.highlight { transform: scale(1.1) !important; border-color: #8ab4f8; box-shadow: 0 0 20px rgba(138, 180, 248, 0.5); background: radial-gradient(circle at 50% 0%, rgba(138, 180, 248, 0.2), rgba(138, 180, 248, 0) 70%), rgba(60, 60, 60, 0.8); }
        .nav-button svg { width: 32px; height: 32px; stroke: #fff; pointer-events: none; }
        .nav-button span { font-size: 0.9rem; font-weight: 500; color: #f5f5f7; pointer-events: none; }
        
        /* Content Panes */
        #content-wrapper { position: fixed; inset: 0; z-index: 900; padding: 2rem; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.5s ease; }
        #content-wrapper.active { opacity: 1; pointer-events: all; }
        .content-pane { width: 100%; max-width: 900px; max-height: 80vh; padding: 32px; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.55); -webkit-backdrop-filter: blur(30px); backdrop-filter: blur(30px); border-radius: var(--border-radius-lg); border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 16px 48px 0 rgba(0, 0, 0, 0.35); overflow-y: auto; }
        .back-button { position: absolute; top: 2rem; left: 2rem; width: 48px; height: 48px; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.7); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.3s ease; z-index: 1001; }
        .back-button:hover { transform: scale(1.1); }
        .back-button svg { width: 24px; height: 24px; stroke: #fff; }
        
        /* List Items */
        .list-item { padding: 20px; margin-bottom: 16px; background: rgba(0, 0, 0, 0.3); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1); cursor: pointer; transition: all 0.3s ease; position: relative; }
        .list-item:hover { transform: translateY(-2px); background: rgba(0, 0, 0, 0.4); border-color: rgba(255, 255, 255, 0.2); }
        .list-item.gesture-hover { transform: translateY(-2px) scale(1.02); background: rgba(0, 0, 0, 0.5); border-color: #8ab4f8; box-shadow: 0 0 20px rgba(138, 180, 248, 0.3); }
        .list-item.gesture-selected { transform: translateY(-2px) scale(1.03); background: rgba(138, 180, 248, 0.1); border-color: #8ab4f8; box-shadow: 0 0 30px rgba(138, 180, 248, 0.5); }
        .list-item h3 { margin-bottom: 8px; color: #f5f5f7; transition: color 0.3s ease; }
        .list-item:hover h3 { color: #8ab4f8; }
        .list-item p { color: #a0a0a5; font-size: 0.9rem; line-height: 1.5; }
        .list-item .meta { margin-top: 8px; font-size: 0.85rem; color: #8ab4f8; }
        
        /* Links */
        a { color: #f5f5f7; text-decoration: none; transition: color 0.3s ease; }
        a:hover { color: #8ab4f8; }
        
        /* Edit Page */
        #edit-page { position: fixed; inset: 0; z-index: 1500; padding: 2rem; display: flex; flex-direction: column; opacity: 0; transform: scale(1.1); pointer-events: none; transition: var(--transition); background: rgba(0,0,0,0.5); -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); color: #e8eaed;}
        #edit-page.visible { opacity: 1; transform: scale(1); pointer-events: all; }
        .edit-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 1.5rem; margin-bottom: 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); flex-shrink: 0;}
        .edit-header h2 { font-size: 1.75rem; font-weight: 600; color: #f5f5f7; }
        .edit-content { display: grid; grid-template-columns: 1fr; gap: 2rem; flex-grow: 1; overflow: hidden; }
        @media (min-width: 768px) { .edit-content { grid-template-columns: 1fr 1fr; } }
        .edit-column { display: flex; flex-direction: column; overflow: hidden; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.55); -webkit-backdrop-filter: blur(30px); backdrop-filter: blur(30px); border-radius: var(--border-radius-lg); border: 1px solid rgba(255, 255, 255, 0.18); box-shadow: 0 16px 48px 0 rgba(0, 0, 0, 0.35); padding: 1.5rem; }
        .edit-column-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
        .edit-column-header h2 { font-size: 1.5rem; color: #f5f5f7;}
        .edit-item-list { overflow-y: auto; }
        .edit-item { background: rgba(0, 0, 0, 0.2); padding: 1.25rem; border-radius: 16px; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255,255,255,0.1); }
        .edit-item-info { flex-grow: 1; overflow: hidden; padding-right: 1rem; } 
        .edit-item-info strong { display: block; font-size: 1.1rem; font-weight: 600; margin-bottom: 0.25rem; } 
        .edit-item-info p { font-size: 0.9rem; color: #a0a0a5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .edit-controls { display: flex; gap: 8px; }
        .icon-button { background: rgba(80, 80, 80, 0.7); border-radius: 50%; border: none; cursor: pointer; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; transition: background-color 0.3s ease; } 
        .icon-button:hover { background: rgba(100, 100, 100, 0.7); } 
        .icon-button svg { stroke: #e0e0e0; width: 16px; height: 16px; }
        .action-button { background: rgba(255,255,255,0.9); border: none; color: #1d1d1f; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-weight: 500; transition: background-color 0.3s ease; } 
        .action-button:hover { background-color: #fff; }
        
        /* Modals */
        .modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); z-index: 2000; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; } 
        .modal-backdrop.visible { opacity: 1; pointer-events: all; } 
        .modal { background: rgba(30, 30, 30, 0.8); border: 1px solid rgba(255,255,255,0.2); border-radius: var(--border-radius-lg); padding: 24px; width: 90%; max-width: 500px; } 
        .modal h2 { margin-top: 0; } 
        .modal input, .modal textarea { width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; padding: 12px; color: #f5f5f7; margin-bottom: 16px; font-family: inherit; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; } 
        .modal-close-btn { background:none; border:none; color:#a0a0a5; font-size: 24px; cursor:pointer; }
        .modal-actions { text-align: right; display: flex; gap: 10px; justify-content: flex-end; }
        .glass-button { border: none; color: #1d1d1f; background-color: rgba(255, 255, 255, 0.85); font-weight: 600; cursor: pointer; padding: 10px 20px; border-radius: 20px; transition: background-color 0.3s ease; } 
        .glass-button:hover { background-color: #fff; }
        .glass-button.secondary { background: rgba(80, 80, 80, 0.7); color: #f5f5f7; border: 1px solid transparent; } 
        .glass-button.secondary:hover { background: rgba(100, 100, 100, 0.7); }
        
        /* FAB Buttons */
        .fab-button { position: fixed; bottom: 32px; z-index: 1000; cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 20px; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(45, 45, 45, 0.65); -webkit-backdrop-filter: blur(25px); backdrop-filter: blur(25px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 50px; box-shadow: 0 8px 24px rgba(0,0,0,0.3); font-weight: 500; font-size: 0.9rem; transition: all 0.3s ease; }
        .fab-button:hover { transform: scale(1.05); }
        .fab-button svg { stroke: #fff; }
        #chat-fab { right: 32px; }
        #catcher-fab { left: 32px; flex-direction: row-reverse; }
        
        /* Chat Window */
        #chat-window { position: fixed; bottom: 95px; right: 32px; width: 380px; max-width: calc(100% - 4rem); height: 520px; z-index: 1600; display: flex; flex-direction: column; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(30, 30, 30, 0.7); -webkit-backdrop-filter: blur(30px); backdrop-filter: blur(30px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: var(--border-radius-lg); box-shadow: 0 16px 48px rgba(0,0,0,0.35); opacity: 0; transform: translateY(20px); pointer-events: none; transition: var(--transition); }
        #chat-window.visible { opacity: 1; transform: translateY(0); pointer-events: all; }
        .chat-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); flex-shrink: 0; }
        .chat-header h3 { font-size: 1rem; }
        .chat-header button { background: none; border: none; color: #a0a0a5; font-size: 24px; cursor: pointer; }
        .chat-messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
        .message { max-width: 85%; padding: 10px 14px; border-radius: 16px; line-height: 1.5; font-size: 0.9rem; }
        .message.user { align-self: flex-end; background: rgba(255, 255, 255, 0.2); color: #f5f5f7; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }
        .message.assistant { align-self: flex-start; background: rgba(80, 80, 80, 0.7); color: #f5f5f7; }
        .message.typing { display: flex; align-items: center; gap: 8px; }
        .typing-dot { width: 8px; height: 8px; background-color: #a0a0a5; border-radius: 50%; animation: typing-bounce 1.2s infinite ease-in-out; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing-bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
        .chat-input-area { padding: 16px; border-top: 1px solid rgba(255, 255, 255, 0.1); flex-shrink: 0; }
        #chat-form { display: flex; gap: 12px; align-items: center; }
        #chat-input { flex: 1; background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.15); color: #f5f5f7; padding: 10px 16px; border-radius: 50px; outline: none; }
        #chat-form button { background: none; border: 1px solid rgba(255, 255, 255, 0.2); width: 40px; height: 40px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background-color 0.3s ease; }
        #chat-form button:hover { background: rgba(255, 255, 255, 0.1); }
        #chat-form button:disabled { opacity: 0.5; cursor: not-allowed; background: none !important; }
        #chat-form button svg { stroke: #fff; }
        
        /* Gesture Catcher Window */
        #catcher-window { position: fixed; bottom: 95px; left: 32px; width: 280px; height: 240px; z-index: 1600; display: flex; flex-direction: column; background: radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0) 70%), rgba(30, 30, 30, 0.7); -webkit-backdrop-filter: blur(30px); backdrop-filter: blur(30px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: var(--border-radius-lg); box-shadow: 0 16px 48px rgba(0,0,0,0.35); opacity: 0; transform: translateY(20px); pointer-events: none; transition: var(--transition); overflow: hidden; }
        #catcher-window.visible { opacity: 1; transform: translateY(0); pointer-events: all; }
        .catcher-header { display: flex; justify-content: flex-end; padding: 8px 12px; position: absolute; top:0; left:0; right:0; z-index: 20;}
        .catcher-header button { background: rgba(0,0,0,0.5); border-radius: 50%; width: 28px; height: 28px; border: none; color: #fff; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center;}
        #output_canvas { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
        .hidden-video { display: none; }
        
        /* Gesture Cursor */
        #gesture-cursor { position: fixed; width: 24px; height: 24px; border: 3px solid #fff; border-radius: 50%; background-color: rgba(255, 255, 255, 0.3); z-index: 9999; pointer-events: none; transform: translate(-50%, -50%); transition: all 0.2s ease; backdrop-filter: blur(2px); opacity: 0; }
        #gesture-cursor.active { opacity: 1; }
        #gesture-cursor.selecting { transform: translate(-50%, -50%) scale(1.5); background-color: rgba(138, 180, 248, 0.6); }
        
        /* Scrollbar */
        .content-pane::-webkit-scrollbar, .chat-messages::-webkit-scrollbar, .edit-item-list::-webkit-scrollbar { width: 14px; }
        .content-pane::-webkit-scrollbar-track, .chat-messages::-webkit-scrollbar-track, .edit-item-list::-webkit-scrollbar-track { background: transparent; }
        .content-pane::-webkit-scrollbar-thumb, .chat-messages::-webkit-scrollbar-thumb, .edit-item-list::-webkit-scrollbar-thumb { background-color: rgba(255, 255, 255, 0); border-radius: 7px; border: 4px solid transparent; background-clip: content-box; }
        .content-pane:hover::-webkit-scrollbar-thumb, .chat-messages:hover::-webkit-scrollbar-thumb, .edit-item-list:hover::-webkit-scrollbar-thumb { background-color: rgba(255, 255, 255, 0.3); }
        
        /* Responsive */
        @media (max-width: 768px) {
            #nav-buttons { grid-template-columns: 1fr; gap: 15px; }
            .nav-button { width: 100px; height: 100px; }
            .nav-button svg { width: 28px; height: 28px; }
            .nav-button span { font-size: 0.8rem; }
            .fab-button span { display: none; }
            .fab-button { padding: 10px; border-radius: 50%; }
            #catcher-window { width: 200px; height: 160px; left: 20px; bottom: 80px; }
            #chat-window { width: calc(100% - 40px); right: 20px; bottom: 80px; }
        }
    </style>
</head>
<body>
    <!-- Gesture Cursor -->
    <div id="gesture-cursor"></div>
    
    <!-- Central Activator -->
    <div id="ui-activator">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
    </div>
    
    <!-- Navigation Buttons -->
    <div id="nav-buttons">
        <div class="nav-button" data-content="profile">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
            <span>Profile</span>
        </div>
        <div class="nav-button" data-content="projects">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
            <span>Projects</span>
        </div>
        <div class="nav-button" data-content="blog">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>Blog</span>
        </div>
        <div class="nav-button" data-content="movies">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect>
                <line x1="7" y1="2" x2="7" y2="22"></line>
                <line x1="17" y1="2" x2="17" y2="22"></line>
                <line x1="2" y1="12" x2="22" y2="12"></line>
                <line x1="2" y1="7" x2="7" y2="7"></line>
                <line x1="2" y1="17" x2="7" y2="17"></line>
                <line x1="17" y1="17" x2="22" y2="17"></line>
                <line x1="17" y1="7" x2="22" y2="7"></line>
            </svg>
            <span>Movies</span>
        </div>
    </div>
    
    <!-- Content Wrapper -->
    <div id="content-wrapper">
        <button class="back-button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
        </button>
        <div id="content-pane" class="content-pane"></div>
    </div>
    
    <!-- Edit Page -->
    <div id="edit-page">
        <div class="edit-header">
            <h2>Management Console</h2>
            <button id="close-edit-page-btn" class="action-button">Return to Hub</button>
        </div>
        <div class="edit-content">
            <div class="edit-column">
                <div class="edit-column-header">
                    <h2>Projects</h2>
                    <button class="action-button" data-type="projects">Add Project</button>
                </div>
                <div id="edit-project-list" class="edit-item-list"></div>
            </div>
            <div class="edit-column">
                <div class="edit-column-header">
                    <h2>Blog</h2>
                    <button class="action-button" data-type="blog">Add Blog Post</button>
                </div>
                <div id="edit-blog-list" class="edit-item-list"></div>
            </div>
        </div>
    </div>
    
    <!-- Edit Modal -->
    <div id="edit-modal" class="modal-backdrop">
        <div class="modal">
            <form id="edit-form">
                <div class="modal-header">
                    <h2 id="edit-modal-title">Edit</h2>
                    <button type="button" class="modal-close-btn">×</button>
                </div>
                <input type="hidden" id="edit-id">
                <input type="hidden" id="edit-type">
                <input type="text" id="edit-title" placeholder="Title" required>
                <textarea id="edit-description" placeholder="Description (Markdown supported)" rows="5"></textarea>
                <input type="text" id="edit-date" placeholder="Date (YYYY-MM-DD)">
                <div class="modal-actions">
                    <button type="button" class="glass-button secondary cancel-button">Cancel</button>
                    <button type="submit" class="glass-button">Save</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Login Modal -->
    <div id="login-modal" class="modal-backdrop">
        <div class="modal">
            <form id="login-form">
                <div class="modal-header">
                    <h2>Authentication</h2>
                    <button type="button" class="modal-close-btn">×</button>
                </div>
                <p style="margin: 0.5rem 0 1rem;">Press 'Esc' to close.</p>
                <input type="password" id="password-input" placeholder="Enter Access Code" required>
                <div class="modal-actions">
                    <button type="submit" class="glass-button">Authenticate</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Gesture Catcher FAB -->
    <button id="catcher-fab" class="fab-button">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path>
            <path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"></path>
            <path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"></path>
            <path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.83l1.76 1.76"></path>
        </svg>
        <span>Catcher</span>
    </button>
    
    <!-- Gesture Catcher Window -->
    <div id="catcher-window">
        <div class="catcher-header">
            <button id="close-catcher-btn">×</button>
        </div>
        <video id="webcam" class="hidden-video" playsinline autoplay muted></video>
        <canvas id="output_canvas"></canvas>
    </div>
    
    <!-- Chat FAB -->
    <button id="chat-fab" class="fab-button">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span>Assistant</span>
    </button>
    
    <!-- Chat Window -->
    <div id="chat-window">
        <div class="chat-header">
            <h3>ZJULIAN Assistant</h3>
            <button id="close-chat-btn">×</button>
        </div>
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-input-area">
            <form id="chat-form">
                <input id="chat-input" placeholder="Ask me anything..." autocomplete="off">
                <button type="submit" id="send-button">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22,2 15,22 11,13 2,9 22,2"></polygon>
                    </svg>
                </button>
            </form>
        </div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        let appData = {};
        const appState = { 
            currentView: 'home', // home, nav, profile, projects, blog, project-detail, blog-detail, movies
            currentDetail: null,
            isAuthenticated: false,
            gestureNavIndex: -1,
            gestureListItemIndex: -1,
            selectedListItem: null,
            mediaPipeLoaded: false 
        };
        const PASSWORD = "admin";
        const PROXY_API_URL = "/api/chat";

        const D = {
            uiActivator: document.getElementById('ui-activator'),
            navButtons: document.getElementById('nav-buttons'),
            contentWrapper: document.getElementById('content-wrapper'),
            contentPane: document.getElementById('content-pane'),
            backButton: document.querySelector('.back-button'),
            chatFab: document.getElementById('chat-fab'),
            chatWindow: document.getElementById('chat-window'),
            closeChatBtn: document.getElementById('close-chat-btn'),
            chatForm: document.getElementById('chat-form'),
            chatInput: document.getElementById('chat-input'),
            chatMessages: document.getElementById('chat-messages'),
            sendButton: document.getElementById('send-button'),
            editPage: document.getElementById('edit-page'),
            closeEditPageBtn: document.getElementById('close-edit-page-btn'),
            editModal: document.getElementById('edit-modal'),
            loginModal: document.getElementById('login-modal'),
            // Gesture elements
            catcherFab: document.getElementById('catcher-fab'),
            catcherWindow: document.getElementById('catcher-window'),
            closeCatcherBtn: document.getElementById('close-catcher-btn'),
            webcam: document.getElementById('webcam'),
            outputCanvas: document.getElementById('output_canvas'),
            gestureCursor: document.getElementById('gesture-cursor'),
        };

        // ==========================================
        // --- GESTURE & MEDIA PIPE INTEGRATION ---
        // ==========================================
        let hands, camera;
        let gestureCooldown = false;
        const PINCH_THRESHOLD = 0.07;
        const handCtx = D.outputCanvas.getContext('2d');

        function getDistance(p1, p2) { 
            if(!p1 || !p2) return Infinity; 
            return Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2) + Math.pow(p1.z - p2.z, 2)); 
        }
        
        function isPinchedIndex(lm) { return getDistance(lm[4], lm[8]) < PINCH_THRESHOLD; }
        function isPinchedMiddle(lm) { return getDistance(lm[4], lm[12]) < PINCH_THRESHOLD; }
        function isPinchedRing(lm) { return getDistance(lm[4], lm[16]) < PINCH_THRESHOLD; }
        function isFist(landmarks) {
            return landmarks[8].y > landmarks[6].y && landmarks[12].y > landmarks[10].y && 
                   landmarks[16].y > landmarks[14].y && landmarks[20].y > landmarks[18].y;
        }

        function updateGestureHighlight() {
            const navButtons = document.querySelectorAll('.nav-button');
            navButtons.forEach((btn, idx) => btn.classList.toggle('highlight', idx === appState.gestureNavIndex));
        }

        function updateListItemHighlight() {
            const listItems = document.querySelectorAll('.list-item');
            listItems.forEach((item, idx) => {
                item.classList.remove('gesture-hover', 'gesture-selected');
                if (idx === appState.gestureListItemIndex) {
                    item.classList.add('gesture-hover');
                }
            });
            if (appState.selectedListItem) {
                appState.selectedListItem.classList.add('gesture-selected');
            }
        }
        
        function handleGesture(gesture) {
            if (gestureCooldown) return;

            if (gesture === 'fist') {
                if (appState.currentView !== 'home' && appState.currentView !== 'nav') {
                    D.backButton.click();
                } else if (appState.currentView === 'nav') {
                    showView('home');
                }
                gestureCooldown = true; 
                setTimeout(() => { gestureCooldown = false; }, 600);
                return;
            }
            
            if (appState.currentView === 'nav') {
                const navButtons = document.querySelectorAll('.nav-button');
                const numButtons = navButtons.length;
                
                if (gesture === 'pinch_index') {
                    appState.gestureNavIndex = (appState.gestureNavIndex <= 0) ? numButtons - 1 : appState.gestureNavIndex - 1;
                    updateGestureHighlight();
                } else if (gesture === 'pinch_ring') {
                    appState.gestureNavIndex = (appState.gestureNavIndex + 1) % numButtons;
                    updateGestureHighlight();
                } else if (gesture === 'pinch_middle' && appState.gestureNavIndex !== -1) {
                    const selectedBtn = document.querySelectorAll('.nav-button')[appState.gestureNavIndex];
                    selectedBtn.click();
                    D.gestureCursor.classList.add('selecting');
                }
            } else if (appState.currentView === 'projects' || appState.currentView === 'blog') {
                const listItems = document.querySelectorAll('.list-item');
                const numItems = listItems.length;
                
                if (gesture === 'pinch_index') {
                    appState.gestureListItemIndex = (appState.gestureListItemIndex <= 0) ? numItems - 1 : appState.gestureListItemIndex - 1;
                    updateListItemHighlight();
                } else if (gesture === 'pinch_ring') {
                    appState.gestureListItemIndex = (appState.gestureListItemIndex + 1) % numItems;
                    updateListItemHighlight();
                } else if (gesture === 'pinch_middle' && appState.gestureListItemIndex !== -1) {
                    const selectedItem = listItems[appState.gestureListItemIndex];
                    if (selectedItem) {
                        appState.selectedListItem = selectedItem;
                        updateListItemHighlight();
                        setTimeout(() => {
                            selectedItem.click();
                            appState.selectedListItem = null;
                        }, 300);
                    }
                }
            }
            
            gestureCooldown = true; 
            setTimeout(() => { gestureCooldown = false; }, 400);
        }

        function onHandsResults(results) {
            handCtx.save();
            handCtx.clearRect(0, 0, D.outputCanvas.width, D.outputCanvas.height);
            handCtx.drawImage(results.image, 0, 0, D.outputCanvas.width, D.outputCanvas.height);

            if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                D.gestureCursor.classList.add('active');
                const landmarks = results.multiHandLandmarks[0];
                
                if (window.drawConnectors && window.drawLandmarks) {
                    drawConnectors(handCtx, landmarks, HAND_CONNECTIONS, { color: 'rgba(0, 255, 0, 0.7)', lineWidth: 2 });
                    drawLandmarks(handCtx, landmarks, { color: 'rgba(255, 0, 0, 0.7)', radius: 3 });
                }

                const indexTip = landmarks[8];
                D.gestureCursor.style.left = `${(1 - indexTip.x) * window.innerWidth}px`;
                D.gestureCursor.style.top = `${indexTip.y * window.innerHeight}px`;

                if (gestureCooldown) { handCtx.restore(); return; }
                
                let cursorColor = 'rgba(255, 255, 255, 0.3)', cursorTransform = 'translate(-50%, -50%) scale(1)';

                if (appState.currentView === 'home' && isPinchedMiddle(landmarks)) {
                    D.uiActivator.click();
                    cursorColor = 'rgba(138, 180, 248, 0.9)';
                    cursorTransform = 'translate(-50%, -50%) scale(2.0)';
                    gestureCooldown = true;
                    setTimeout(() => { gestureCooldown = false; }, 1000);
                } else if (isFist(landmarks)) {
                    handleGesture('fist');
                    cursorColor = 'rgba(255, 140, 0, 0.8)';
                    cursorTransform = 'translate(-50%, -50%) scale(1.4)';
                } else if (isPinchedMiddle(landmarks)) {
                    handleGesture('pinch_middle');
                    cursorColor = 'rgba(236, 72, 153, 0.8)';
                    cursorTransform = 'translate(-50%, -50%) scale(1.5)';
                    D.gestureCursor.classList.add('selecting');
                } else if (isPinchedIndex(landmarks)) {
                    handleGesture('pinch_index');
                    cursorColor = 'rgba(59, 130, 246, 0.8)';
                    cursorTransform = 'translate(-50%, -50%) scale(1.2)';
                } else if (isPinchedRing(landmarks)) {
                    handleGesture('pinch_ring');
                    cursorColor = 'rgba(34, 197, 94, 0.8)';
                    cursorTransform = 'translate(-50%, -50%) scale(1.2)';
                } else {
                    D.gestureCursor.classList.remove('selecting');
                }
                D.gestureCursor.style.backgroundColor = cursorColor;
                D.gestureCursor.style.transform = cursorTransform;
            } else {
                D.gestureCursor.classList.remove('active', 'selecting');
            }
            handCtx.restore();
        }

        async function loadMediaPipeAndStart() {
            if (appState.mediaPipeLoaded) { startCamera(); return; }
            const scripts = ["camera_utils", "control_utils", "drawing_utils", "hands"];
            try {
                await Promise.all(scripts.map(name => new Promise((resolve, reject) => {
                    const s = document.createElement('script');
                    s.src = `https://cdn.jsdelivr.net/npm/@mediapipe/${name}/${name}.js`;
                    s.crossOrigin = "anonymous";
                    s.onload = resolve; 
                    s.onerror = reject; 
                    document.head.appendChild(s);
                })));
                appState.mediaPipeLoaded = true;
                hands = new Hands({ locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}` });
                hands.setOptions({ maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: 0.7, minTrackingConfidence: 0.7 });
                hands.onResults(onHandsResults);
                startCamera();
            } catch (e) { 
                console.error("Failed to load MediaPipe:", e); 
                alert("Gesture system failed to load."); 
            }
        }

        async function startCamera() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
                D.webcam.srcObject = stream;
                D.webcam.onloadedmetadata = () => {
                    D.outputCanvas.width = D.webcam.videoWidth;
                    D.outputCanvas.height = D.webcam.videoHeight;
                    camera = new Camera(D.webcam, {
                        onFrame: async () => await hands.send({ image: D.webcam }),
                        width: D.webcam.videoWidth, 
                        height: D.webcam.videoHeight
                    });
                    camera.start();
                };
            } catch (err) { 
                stopCamera(); 
                alert("Could not access camera."); 
            }
        }

        function stopCamera() {
            if (camera) { camera.stop(); camera = null; }
            if (D.webcam.srcObject) { 
                D.webcam.srcObject.getTracks().forEach(track => track.stop()); 
                D.webcam.srcObject = null; 
            }
            D.gestureCursor.classList.remove('active', 'selecting');
            D.catcherWindow.classList.remove('visible');
        }

        // ==========================================
        // --- CORE APP LOGIC ---
        // ==========================================
        function showView(view, detailId = null) {
            // Hide all views
            D.uiActivator.classList.add('hidden');
            D.navButtons.classList.remove('active');
            D.contentWrapper.classList.remove('active');
            D.editPage.classList.remove('visible');
            
            // Reset gesture navigation
            appState.gestureNavIndex = -1;
            appState.gestureListItemIndex = -1;
            appState.selectedListItem = null;
            updateGestureHighlight();
            updateListItemHighlight();
            
            appState.currentView = view;
            appState.currentDetail = detailId;

            // Show specific view
            switch(view) {
                case 'home':
                    D.uiActivator.classList.remove('hidden');
                    break;
                case 'nav':
                    D.navButtons.classList.add('active');
                    break;
                case 'profile':
                case 'projects':
                case 'blog':
                case 'project-detail':
                case 'blog-detail':
                    D.contentWrapper.classList.add('active');
                    setTimeout(() => renderContent(view, detailId), 50);
                    break;
                case 'movies':
                    window.location.href = '/movies';
                    break;
                case 'edit':
                    D.editPage.classList.add('visible');
                    renderEditPage();
                    break;
            }
        }

        function renderContent(type, detailId = null) {
            let html = '';
            switch(type) {
                case 'profile':
                    const a = appData.about;
                    html = `
                        <h1 style="margin-bottom: 24px;">Agent Profile</h1>
                        <h2>${a.profile.NAME}</h2>
                        <p style="margin: 16px 0;"><strong>CLASSIFICATION:</strong> ${a.profile.CLASSIFICATION}<br><strong>STATUS:</strong> ${a.profile.STATUS}</p>
                        <h3 style="margin-top: 32px;">Core Systems</h3>
                        <ul style="margin-top: 16px;">${a.systems.map(s => `<li style="margin-bottom: 8px;">• ${s}</li>`).join('')}</ul>
                        <h3 style="margin-top: 32px;">Secure Channels</h3>
                        <ul style="margin-top: 16px;">
                            <li style="margin-bottom: 8px;">• <a href="${a.channels.GitHub}" target="_blank">GitHub</a></li>
                            <li style="margin-bottom: 8px;">• <a href="${a.channels.LinkedIn}" target="_blank">LinkedIn</a></li>
                            <li style="margin-bottom: 8px;">• <a href="mailto:${a.channels.Email}">Email</a></li>
                        </ul>
                    `;
                    break;
                case 'projects':
                    html = '<h1 style="margin-bottom: 24px;">Projects</h1>';
                    (appData.projects || []).forEach(p => {
                        html += `
                            <div class="list-item" data-id="${p.id}">
                                <h3>${p.title}</h3>
                                <p>${p.description.substring(0, 150)}...</p>
                            </div>
                        `;
                    });
                    break;
                case 'project-detail':
                    const project = (appData.projects || []).find(p => p.id === detailId);
                    if (project) {
                        html = `
                            <h1 style="margin-bottom: 24px;">${project.title}</h1>
                            <div style="line-height: 1.8; color: #d1d1d6; font-size: 1.05rem;">
                                ${marked.parse(project.description || 'No description available.')}
                            </div>
                            <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.1);">
                                <p style="color: #8ab4f8; font-size: 0.9rem;">Project ID: ${project.id}</p>
                            </div>
                        `;
                    }
                    break;
                case 'blog':
                    html = '<h1 style="margin-bottom: 24px;">Blog</h1>';
                    (appData.blog || []).forEach(b => {
                        html += `
                            <div class="list-item" data-id="${b.id}">
                                <h3>${b.title}</h3>
                                <p style="color: #8ab4f8; font-size: 0.85rem; margin-bottom: 8px;">${b.date || ''}</p>
                                <p>${(b.description || '').replace(/<[^>]*>/g, '').substring(0, 150)}...</p>
                            </div>
                        `;
                    });
                    break;
                case 'blog-detail':
                    const blog = (appData.blog || []).find(b => b.id === detailId);
                    if (blog) {
                        html = `
                            <h1 style="margin-bottom: 24px;">${blog.title}</h1>
                            <p style="color: #8ab4f8; margin-bottom: 24px;">${blog.date || ''}</p>
                            <div style="line-height: 1.8; color: #d1d1d6; font-size: 1.05rem;">
                                ${marked.parse(blog.description || 'No content available.')}
                            </div>
                        `;
                    }
                    break;
            }
            D.contentPane.innerHTML = html;
        }

        function renderEditPage() {
            let projectsHTML = '', blogHTML = '';
            (appData.projects || []).forEach(p => {
                projectsHTML += `
                    <div class="edit-item">
                        <div class="edit-item-info">
                            <strong>${p.title}</strong>
                            <p>${p.description.substring(0,80)}...</p>
                        </div>
                        <div class="edit-controls" data-id="${p.id}" data-type="projects">
                            <button class="icon-button edit-button">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                            <button class="icon-button delete-button">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                `;
            });
            (appData.blog || []).forEach(b => {
                blogHTML += `
                    <div class="edit-item">
                        <div class="edit-item-info">
                            <strong>${b.title}</strong>
                            <p>${b.date}</p>
                        </div>
                        <div class="edit-controls" data-id="${b.id}" data-type="blog">
                            <button class="icon-button edit-button">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                            </button>
                            <button class="icon-button delete-button">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                `;
            });
            document.getElementById('edit-project-list').innerHTML = projectsHTML;
            document.getElementById('edit-blog-list').innerHTML = blogHTML;
        }

        function showTypingIndicator() {
            const el = document.createElement('div');
            el.classList.add('message', 'assistant', 'typing');
            el.innerHTML = `<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>`;
            D.chatMessages.appendChild(el);
            D.chatMessages.scrollTop = D.chatMessages.scrollHeight;
            return el;
        }
        
        function appendMessage(text, type, isNew = true) {
            const el = document.createElement('div');
            el.classList.add('message', type);
            el.innerHTML = (type === 'assistant' && isNew) ? marked.parse(text) : text;
            D.chatMessages.appendChild(el);
            D.chatMessages.scrollTop = D.chatMessages.scrollHeight;
        }

        function showModal(modal) {
            modal.classList.add('visible');
        }
        
        function hideModal(modal) {
            modal.classList.remove('visible');
        }
        
        function openEditModal(type, id) {
            const isNew = !id;
            const item = isNew ? {} : appData[type].find(i => i.id === id);
            const form = document.getElementById('edit-form');
            form.reset();
            
            form.querySelector('#edit-modal-title').textContent = isNew ? 
                `Add New ${type === 'projects' ? 'Project' : 'Blog Post'}` : 
                `Edit ${type === 'projects' ? 'Project' : 'Blog Post'}`;
            form.querySelector('#edit-id').value = id || '';
            form.querySelector('#edit-type').value = type;
            form.querySelector('#edit-title').value = item.title || '';
            form.querySelector('#edit-description').value = item.description || '';
            form.querySelector('#edit-date').value = item.date || '';
            
            form.querySelector('#edit-description').style.display = 'block';
            form.querySelector('#edit-date').style.display = type === 'blog' ? 'block' : 'none';
            
            showModal(D.editModal);
        }

        // ==========================================
        // --- INITIALIZATION ---
        // ==========================================
        const initializeApp = async () => {
            try {
                const r = await fetch('/load_data');
                if (!r.ok) throw new Error('Network fail');
                appData = await r.json();
                
                // Add sample data if empty
                if (!appData.about) {
                    appData.about = {
                        profile: { NAME: "ZJULIAN", CLASSIFICATION: "Advanced AI Agent", STATUS: "ACTIVE" },
                        systems: ["Neural Network Core", "Quantum Processing Unit", "Adaptive Learning Algorithm", "Secure Data Vault"],
                        channels: { GitHub: "https://github.com/zjulian", LinkedIn: "https://linkedin.com/in/zjulian", Email: "contact@zjulian.ai" }
                    };
                }
                
                if (!appData.projects || appData.projects.length === 0) {
                    appData.projects = [
                        { 
                            id: 'proj_1', 
                            title: 'AI-Powered Analytics Platform', 
                            description: `## Overview\\n\\nA comprehensive analytics solution leveraging machine learning algorithms to provide real-time insights and predictive modeling.` 
                        },
                        { 
                            id: 'proj_2', 
                            title: 'Blockchain Supply Chain Tracker', 
                            description: `## Introduction\\n\\nA decentralized supply chain management system using blockchain technology to ensure transparency and traceability.`
                        }
                    ];
                }
                
                if (!appData.blog || appData.blog.length === 0) {
                    appData.blog = [
                        { 
                            id: 'blog_1', 
                            title: 'The Future of Quantum Computing', 
                            date: '2023-10-15', 
                            description: `## Introduction\\n\\nQuantum computing represents a paradigm shift in computational capabilities.`
                        },
                        { 
                            id: 'blog_2', 
                            title: 'Building Scalable Microservices', 
                            date: '2023-09-28', 
                            description: `## Overview\\n\\nMicroservices architecture has become the de facto standard for building scalable, maintainable applications.`
                        }
                    ];
                }
                
                await fetch('/save_data', { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(appData) 
                });
                
                // Load chat history
                try {
                    const chatHistory = await (await fetch('/load_chat')).json();
                    D.chatMessages.innerHTML = '';
                    chatHistory.forEach(msg => appendMessage(msg.content, msg.role, false));
                } catch(e) {
                    console.log('No chat history found');
                }
            } catch (error) {
                console.error("Init Error:", error);
            }

            addEventListeners();
        };

        function addEventListeners() {
            D.uiActivator.addEventListener('click', () => showView('nav'));
            
            D.navButtons.addEventListener('click', (e) => {
                const button = e.target.closest('.nav-button');
                if (button) {
                    const contentType = button.dataset.content;
                    showView(contentType);
                } else if (e.target === D.navButtons) {
                    showView('home');
                }
            });

            D.contentPane.addEventListener('click', (e) => {
                if (appState.currentView !== 'projects' && appState.currentView !== 'blog') {
                    return;
                }
                const item = e.target.closest('.list-item');
                if (item) {
                    const id = item.dataset.id;
                    if (id) {
                        const detailView = appState.currentView === 'projects' ? 'project-detail' : 'blog-detail';
                        showView(detailView, id);
                    }
                }
            });
            
            D.backButton.addEventListener('click', () => {
                if (appState.currentView === 'project-detail' || appState.currentView === 'blog-detail') {
                    showView(appState.currentView === 'project-detail' ? 'projects' : 'blog');
                } else {
                    showView('nav');
                }
            });
            
            D.chatFab.addEventListener('click', () => D.chatWindow.classList.add('visible'));
            D.closeChatBtn.addEventListener('click', () => D.chatWindow.classList.remove('visible'));
            
            D.catcherFab.addEventListener('click', () => { 
                D.catcherWindow.classList.add('visible'); 
                loadMediaPipeAndStart(); 
            });
            D.closeCatcherBtn.addEventListener('click', stopCamera);
            
            D.chatForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const userInput = D.chatInput.value.trim();
                if(!userInput) return;
                
                if (userInput === '###zjulianedit') {
                    if (!appState.isAuthenticated) {
                        showModal(D.loginModal);
                    } else {
                        showView('edit');
                    }
                    D.chatInput.value = '';
                    return;
                }
                
                appendMessage(userInput, 'user');
                await fetch('/save_chat', { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({role: 'user', content: userInput}) 
                });
                
                D.chatInput.value = '';
                D.sendButton.disabled = true;
                const typingEl = showTypingIndicator();
                
                try {
                    const chatHistory = await (await fetch('/load_chat')).json();
                    const messagesForApi = chatHistory.map(msg => ({ role: msg.role, content: msg.content }));
                    const response = await fetch(PROXY_API_URL, { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }, 
                        body: JSON.stringify({ messages: messagesForApi }) 
                    });
                    
                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(`API Error: ${response.status} - ${err.error.message}`);
                    }
                    
                    const data = await response.json();
                    const assistantReply = data.choices?.[0]?.message?.content || "Sorry, I couldn't get a proper response.";
                    
                    typingEl.remove();
                    appendMessage(assistantReply, 'assistant');
                    await fetch('/save_chat', { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }, 
                        body: JSON.stringify({role: 'assistant', content: assistantReply}) 
                    });
                } catch(err) {
                    console.error("Chat API Error:", err);
                    typingEl.remove();
                    const errorMsg = "Sorry, an error occurred.";
                    appendMessage(errorMsg, 'assistant');
                    await fetch('/save_chat', { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }, 
                        body: JSON.stringify({role: 'assistant', content: errorMsg}) 
                    });
                } finally {
                    D.sendButton.disabled = false;
                }
            });
            
            D.closeEditPageBtn.addEventListener('click', () => showView('nav'));
            
            document.getElementById('login-form').addEventListener('submit', (e) => {
                e.preventDefault();
                if (document.getElementById('password-input').value === PASSWORD) {
                    appState.isAuthenticated = true;
                    hideModal(D.loginModal);
                } else {
                    alert('Access Denied.');
                }
                e.target.reset();
            });
            
            document.getElementById('edit-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const form = e.target;
                const id = form.querySelector('#edit-id').value;
                const type = form.querySelector('#edit-type').value;
                let dateValue = form.querySelector('#edit-date').value;
                
                if (type === 'blog' && !dateValue && !id) {
                    dateValue = new Date().toISOString().split('T')[0];
                }
                
                const entryData = { 
                    title: form.querySelector('#edit-title').value, 
                    description: form.querySelector('#edit-description').value, 
                    date: dateValue 
                };
                
                if(id) {
                    Object.assign(appData[type].find(item => item.id === id), entryData);
                } else {
                    entryData.id = `${type.slice(0,4)}_${Date.now()}`;
                    appData[type].push(entryData);
                }
                
                await fetch('/save_data', { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify(appData) 
                });
                
                renderEditPage();
                hideModal(D.editModal);
            });
            
            D.editPage.addEventListener('click', (e) => {
                const addBtn = e.target.closest('.action-button[data-type]');
                const editBtn = e.target.closest('.edit-button');
                const deleteBtn = e.target.closest('.delete-button');
                
                if(addBtn) openEditModal(addBtn.dataset.type);
                
                if(editBtn) {
                    const controls = editBtn.closest('.edit-controls');
                    openEditModal(controls.dataset.type, controls.dataset.id);
                }
                
                if(deleteBtn) {
                    if(confirm('Are you sure?')) {
                        const controls = deleteBtn.closest('.edit-controls');
                        appData[controls.dataset.type] = appData[controls.dataset.type].filter(item => item.id !== controls.dataset.id);
                        fetch('/save_data', { 
                            method: 'POST', 
                            headers: { 'Content-Type': 'application/json' }, 
                            body: JSON.stringify(appData) 
                        }).then(renderEditPage);
                    }
                }
            });
            
            document.querySelectorAll('.modal-close-btn, .cancel-button').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const modal = e.target.closest('.modal-backdrop');
                    hideModal(modal);
                });
            });
            
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    if (appState.currentView === 'home') showModal(D.loginModal);
                    else if (appState.currentView !== 'nav' && appState.currentView !== 'home') showView('nav');
                    else if (appState.currentView === 'nav') showView('home');
                }
            });
        }

        initializeApp();
    });
    </script>
</body>
</html>
"""

# 电影墙主页
HTML_MOVIES_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的电影回忆墙</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @keyframes background-zoom { 0% { transform: scale(1); } 100% { transform: scale(1.1); } }
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes fade-in-up { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes fade-out { to { opacity: 0; transform: scale(0.95); } }
        html, body { scroll-behavior: smooth; }
        body { font-family: 'Inter', sans-serif; background-color: #000; overflow-x: hidden; }
        #background-container { position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: -1; transition: opacity 1.5s ease-in-out; }
        .background-image { position: absolute; top: -5%; left: -5%; width: 110%; height: 110%; background-size: cover; background-position: center; filter: blur(16px) brightness(0.5); animation: background-zoom 40s ease-in-out infinite alternate, fade-in 1.5s ease-in-out; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(120, 113, 108, 0.4); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(120, 113, 108, 0.6); }

        #movie-wall { perspective: 1500px; }
        .movie-card { transform-style: preserve-3d; transition: transform 0.2s ease-out, box-shadow 0.3s ease; position: relative; }
        .movie-card:hover { z-index: 10; }
        .movie-card.spotlight { box-shadow: 0 0 60px 15px rgba(234, 179, 8, 0.5); transform: scale(1.05) !important; z-index: 20; }
        .movie-card.dimmed { opacity: 0.2; filter: blur(4px); transition: opacity 0.5s ease, filter 0.5s ease; }
        .movie-card .poster-image-wrapper { transform-style: preserve-3d; transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1); }
        .movie-card:hover .poster-image-wrapper { transform: translateZ(30px); }
        .movie-info { opacity: 0; transition: opacity 0.4s ease; transform: translateY(10px); }
        .movie-card:hover .movie-info { opacity: 1; transform: translateY(0); }
        .delete-btn { opacity: 0; transition: opacity 0.3s ease; }
        .movie-card:hover .delete-btn { opacity: 1; }
        .movie-card.fading-out { animation: fade-out 0.4s ease forwards; }
        
        .crystal-glass { background: rgba(18, 18, 18, 0.6); backdrop-filter: blur(40px) saturate(150%); -webkit-backdrop-filter: blur(40px) saturate(150%); border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1) inset; }
        .modal-backdrop { transition: opacity 0.4s ease; }
        
        .action-btn { background-color: rgba(28, 28, 30, 0.6); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); transition: all 0.2s; }
        .action-btn:hover:not(:disabled) { background-color: rgba(40, 40, 42, 0.7); border-color: rgba(255, 255, 255, 0.2); transform: scale(1.05); }
        .action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .tab-btn { transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1); }
        .tab-btn.active { background: rgba(30, 30, 32, 0.7); backdrop-filter: blur(24px) saturate(150%); -webkit-backdrop-filter: blur(24px) saturate(150%); border: 1px solid rgba(255, 255, 255, 0.1); }
        .card-enter-animation { animation: fade-in-up 0.6s cubic-bezier(0.25, 1, 0.5, 1) forwards; opacity: 0; }

        #movie-wall.view-collage { display: block; column-count: 5; column-gap: 1rem; }
        @media (max-width: 1280px) { #movie-wall.view-collage { column-count: 4; } }
        @media (max-width: 1024px) { #movie-wall.view-collage { column-count: 3; } }
        @media (max-width: 768px) { #movie-wall.view-collage { column-count: 2; } }
        .collage-item { position: relative; break-inside: avoid; margin-bottom: 1rem; overflow: hidden; border-radius: 0.5rem; }
        .collage-item img { width: 100%; height: auto; display: block; }
        .collage-info { position: absolute; bottom: 0; left: 0; right: 0; padding: 0.75rem 0.5rem; background: linear-gradient(to top, rgba(0,0,0,0.85), transparent); color: white; opacity: 0; transform: translateY(100%); transition: opacity 0.3s ease, transform 0.3s ease; }
        .collage-item:hover .collage-info { opacity: 1; transform: translateY(0); }

        .search-modal-item:hover { background-color: rgba(255, 255, 255, 0.05); }
        .line-clamp-2 { overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
    </style>
</head>
<body class="text-gray-300 antialiased">
    <div id="background-container"></div>

    <a href="/" class="action-btn fixed top-4 left-4 z-20 w-11 h-11 flex items-center justify-center rounded-full" title="返回主页">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
    </a>

    <button id="settingsBtn" class="action-btn fixed top-4 right-4 z-20 w-11 h-11 flex items-center justify-center rounded-full" title="设置">
        <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
    </button>

    <div class="container mx-auto p-4 sm:p-6 lg:p-8 relative z-10">
        <header class="text-center mb-8">
            <h1 class="text-4xl sm:text-5xl font-bold text-white tracking-tight" style="text-shadow: 0 0 30px rgba(234, 179, 8, 0.4);">我的电影回忆墙</h1>
            <p class="mt-3 text-lg text-amber-100 opacity-70">Flask 整合版</p>
            
            <div class="mt-8 max-w-2xl mx-auto">
                <div class="relative">
                    <input type="search" id="searchInput" placeholder="搜索电影或剧集以添加到列表..." class="w-full py-3 pl-4 pr-12 bg-black/20 border border-white/10 rounded-xl focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none transition text-white">
                    <button id="searchBtn" class="absolute inset-y-0 right-0 flex items-center pr-4 text-stone-400 hover:text-white">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    </button>
                </div>
            </div>

            <div class="mt-6 flex justify-center items-center gap-4">
                <label for="fileUpload" class="action-btn inline-flex items-center gap-2 py-3 px-6 rounded-xl cursor-pointer">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                    上传表格
                </label>
                <input type="file" id="fileUpload" class="hidden" accept=".xlsx">
                <button id="inspirationBtn" class="action-btn inline-flex items-center gap-2 py-3 px-6 rounded-xl">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2.1c.2-.5.5-.9.9-1.1.4-.3.8-.4 1.3-.4s1 .2 1.4.5c.4.3.7.7.9 1.2l.2 1c.2.7.5 1.2 1 1.6.5.4 1 .7 1.7.9l1 .2c.5.2.9.5 1.1.9.3.4.4.8.4 1.3s-.2 1-.5 1.4c-.3.4-.7.7-1.2.9l-1 .2c-.7.2-1.2.5-1.6 1-.4.5-.7 1-.9 1.7l-.2 1c-.2.5-.5.9-.9 1.1-.4.3-.8.4-1.3-.4s-1-.2-1.4-.5c-.4-.3-.7-.7-.9-1.2l-.2-1c-.2-.7-.5-1.2-1-1.6-.5-.4-1-.7-1.7-.9l-1-.2c-.5-.2-.9-.5-1.1-.9-.3-.4-.4-.8-.4-1.3s.2-1 .5-1.4c.3-.4.7-.7 1.2-.9l1-.2c.7-.2 1.2-.5 1.6-1 .4-.5.7-1 .9-1.7Z"/><path d="M2.6 10.4c.2-.5.5-.9.9-1.1.4-.3.8-.4 1.3-.4s1 .2 1.4.5c.4.3.7.7.9 1.2l.2 1c.2.7.5 1.2 1 1.6.5.4 1 .7 1.7.9l1 .2c.5.2.9.5 1.1.9.3.4.4.8.4 1.3s-.2 1-.5 1.4c-.3.4-.7.7-1.2.9l-1 .2c-.7.2-1.2.5-1.6 1-.4.5-.7 1-.9 1.7l-.2 1c-.2.5-.5.9-.9 1.1-.4.3-.8.4-1.3-.4s-1-.2-1.4-.5c-.4-.3-.7-.7-.9-1.2l-.2-1c-.2-.7-.5-1.2-1-1.6-.5-.4-1-.7-1.7-.9l-1-.2c-.5-.2-.9-.5-1.1-.9-.3-.4-.4-.8-.4-1.3s.2-1 .5-1.4c.3-.4.7-.7 1.2-.9l1-.2c.7-.2 1.2-.5 1.6-1 .4-.5.7-1 .9-1.7Z"/></svg>
                    灵感
                </button>
            </div>
            <p id="statusMessage" class="text-sm text-stone-400 mt-3 h-5 text-center"></p>
        </header>

        <div class="flex justify-center items-center mb-10">
            <div id="tabs" class="relative flex justify-center items-center p-1 rounded-xl border border-white/10 bg-black/20">
                <button data-status="watched" class="tab-btn active rounded-lg px-4 py-2 font-medium text-white relative z-10">已看</button>
                <button data-status="watching" class="tab-btn rounded-lg px-4 py-2 font-medium text-stone-400 hover:text-white relative z-10">在看</button>
                <button data-status="wantToWatch" class="tab-btn rounded-lg px-4 py-2 font-medium text-stone-400 hover:text-white relative z-10">想看</button>
            </div>
            <button id="viewToggleBtn" class="action-btn ml-4 p-3 rounded-xl flex items-center justify-center" title="切换视图">
                <svg id="gridIcon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                <svg id="collageIcon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="hidden"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
            </button>
        </div>

        <div id="movie-wall" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 sm:gap-8"></div>
    </div>

    <!-- Modals -->
    <div id="searchModal" class="fixed inset-0 bg-black bg-opacity-80 flex items-start justify-center p-4 z-50 hidden modal-backdrop">
        <div id="searchPanel" class="w-full max-w-2xl crystal-glass rounded-2xl p-1 mt-36 relative">
            <div id="searchResultsContainer" class="max-h-[60vh] overflow-y-auto p-3"></div>
            <button id="closeSearchModalBtn" class="absolute top-3 right-3 text-stone-400 hover:text-white text-2xl">&times;</button>
        </div>
    </div>

    <div id="confirmDeleteModal" class="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center p-4 z-50 hidden modal-backdrop">
        <div class="w-full max-w-sm crystal-glass rounded-2xl p-6 text-center">
            <h3 class="text-lg font-bold text-white">确认删除</h3>
            <p class="text-stone-300 mt-2">你确定要从列表中删除这部电影吗？此操作无法撤销。</p>
            <div class="mt-6 flex justify-center gap-4">
                <button id="cancelDeleteBtn" class="py-2 px-6 rounded-lg bg-stone-600/50 hover:bg-stone-500/50 text-white">取消</button>
                <button id="confirmDeleteBtn" class="py-2 px-6 rounded-lg bg-red-600/80 hover:bg-red-500/80 text-white">删除</button>
            </div>
        </div>
    </div>

    <div id="settingsModal" class="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center p-4 z-50 hidden modal-backdrop">
        <div class="w-full max-w-md crystal-glass rounded-2xl p-6 relative">
            <h3 class="text-xl font-bold text-white mb-6">设置</h3>
            <div class="space-y-4">
                <div>
                    <label for="taglineLang" class="font-medium text-stone-200">宣传语语言偏好</label>
                    <select id="taglineLang" class="w-full mt-1 p-2 bg-black/20 border border-white/10 rounded-lg focus:ring-2 focus:ring-amber-400 outline-none">
                        <option value="zh-CN">中文</option>
                        <option value="en-US">英文</option>
                    </select>
                </div>
                <div>
                    <label for="posterLang" class="font-medium text-stone-200">海报语言偏好</label>
                    <select id="posterLang" class="w-full mt-1 p-2 bg-black/20 border border-white/10 rounded-lg focus:ring-2 focus:ring-amber-400 outline-none">
                        <option value="zh,en,null">优先中文</option>
                        <option value="en,zh,null">优先英文</option>
                    </select>
                </div>
                 <div class="pt-4">
                    <h4 class="font-medium text-stone-200">数据管理</h4>
                    <button id="clearCacheBtn" class="w-full mt-2 py-2 px-4 rounded-lg bg-red-800/60 hover:bg-red-700/60 text-white border border-red-500/50">清空所有电影数据</button>
                    <p class="text-xs text-stone-400 mt-1">此操作将删除所有列表，请谨慎操作。</p>
                </div>
            </div>
            <button id="closeSettingsBtn" class="absolute top-4 right-4 text-stone-400 hover:text-white text-2xl">&times;</button>
        </div>
    </div>

    <script>
        // --- CONFIG ---
        const API_BASE_URL = ''; // Relative path to our own Flask server
        const TMDB_IMAGE_BASE_URL_JS = 'https://image.tmdb.org/t/p/w500';

        // --- STATE ---
        let movieLists = { watched: [], watching: [], wantToWatch: [] };
        let currentStatus = 'watched';
        let currentView = 'grid';

        // --- DOM ELEMENTS ---
        const dom = {
            backgroundContainer: document.getElementById('background-container'),
            movieWall: document.getElementById('movie-wall'),
            fileUpload: document.getElementById('fileUpload'),
            statusMessage: document.getElementById('statusMessage'),
            tabs: document.getElementById('tabs'),
            viewToggleBtn: document.getElementById('viewToggleBtn'),
            gridIcon: document.getElementById('gridIcon'),
            collageIcon: document.getElementById('collageIcon'),
            inspirationBtn: document.getElementById('inspirationBtn'),
            searchInput: document.getElementById('searchInput'),
            searchBtn: document.getElementById('searchBtn'),
            searchModal: document.getElementById('searchModal'),
            searchResultsContainer: document.getElementById('searchResultsContainer'),
            closeSearchModalBtn: document.getElementById('closeSearchModalBtn'),
            confirmDeleteModal: document.getElementById('confirmDeleteModal'),
            confirmDeleteBtn: document.getElementById('confirmDeleteBtn'),
            cancelDeleteBtn: document.getElementById('cancelDeleteBtn'),
            settingsBtn: document.getElementById('settingsBtn'),
            settingsModal: document.getElementById('settingsModal'),
            closeSettingsBtn: document.getElementById('closeSettingsBtn'),
            taglineLangSelect: document.getElementById('taglineLang'),
            posterLangSelect: document.getElementById('posterLang'),
            clearCacheBtn: document.getElementById('clearCacheBtn')
        };

        // --- DATA & API CALLS ---
        async function fetchMovieData() {
            setStatus('正在从服务器获取数据...');
            try {
                const response = await fetch(`/api/movies`);
                if (!response.ok) {
                    const errorHeader = response.headers.get('X-Error') || '未知服务器错误';
                    throw new Error(`服务器响应错误: ${response.status} - ${errorHeader}`);
                }
                movieLists = await response.json();
                setStatus('数据加载成功！', 3000);
                render();
                updateDynamicBackground();
            } catch (error) {
                console.error('获取电影数据失败:', error);
                setStatus(`获取数据失败: ${error.message}`);
                render(); 
            }
        }

        async function handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            setStatus('正在上传并从TMDB获取详细信息，请耐心等待...');

            try {
                const response = await fetch(`/api/upload`, {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.detail || '上传失败');
                }
                setStatus(result.message, 5000);
                await fetchMovieData();
            } catch (error) {
                setStatus(`上传失败: ${error.message}`);
                console.error('上传错误:', error);
            }
        }

        async function handleSearch() {
            const query = dom.searchInput.value.trim();
            if (!query) return;
            setStatus(`正在搜索 "${query}"...`);
            try {
                const response = await fetch(`/api/search?query=${encodeURIComponent(query)}`);
                if (!response.ok) throw new Error('搜索请求失败');
                const results = await response.json();
                renderSearchResults(results);
                setStatus('');
            } catch (error) {
                setStatus(`搜索出错: ${error.message}`);
            }
        }

        async function handleAddMovie(e) {
            const target = e.target.closest('.add-btn');
            if (!target || target.disabled) return;

            const { tmdbId, mediaType, list } = target.dataset;
            const originalText = target.textContent;
            target.disabled = true;
            target.textContent = '添加中...';

            try {
                const response = await fetch(`/api/add`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tmdb_id: parseInt(tmdbId), media_type: mediaType, target_list: list })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || '添加失败');
                
                setStatus(result.message, 5000);
                closeSearchModal();
                await fetchMovieData();

            } catch (error) {
                setStatus(`添加失败: ${error.message}`, 5000);
                target.disabled = false;
                target.textContent = originalText;
            }
        }
        
        async function deleteMovie(listName, movieId) {
            try {
                const response = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ list_name: listName, movie_id: movieId })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || '删除失败');
                
                setStatus(result.message, 3000);
                // Visually remove the card
                const cardToRemove = document.querySelector(`.movie-card[data-movie-id="${movieId}"]`);
                if (cardToRemove) {
                    cardToRemove.classList.add('fading-out');
                    setTimeout(() => {
                        cardToRemove.remove();
                        // Update local state to prevent it from reappearing on re-render
                        const movieIndex = movieLists[listName].findIndex(m => m.id === movieId);
                        if (movieIndex > -1) {
                            movieLists[listName].splice(movieIndex, 1);
                        }
                    }, 400);
                }
            } catch (error) {
                setStatus(`删除失败: ${error.message}`);
            }
        }

        // --- RENDER & UI ---
        function setStatus(message, clearAfter = 0) {
            dom.statusMessage.textContent = message;
            if (clearAfter > 0) {
                setTimeout(() => {
                    if (dom.statusMessage.textContent === message) {
                        dom.statusMessage.textContent = '';
                    }
                }, clearAfter);
            }
        }

        function render() {
            resetSpotlight();
            const isCollage = currentView === 'collage';
            dom.movieWall.className = isCollage 
                ? 'view-collage' 
                : 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 sm:gap-8';

            if (isCollage) renderCollageView();
            else renderGridView();
        }

        function renderGridView() {
            dom.movieWall.innerHTML = ''; 
            const currentMovieList = movieLists[currentStatus] || [];
            if (currentMovieList.length === 0) {
                dom.movieWall.innerHTML = `<div class="col-span-full text-center py-16 px-4"><p class="text-stone-400">这个列表里还没有电影哦。请先上传一个表格或通过搜索添加。</p></div>`;
                updateInspirationBtn(); return;
            }
            currentMovieList.forEach((movie, index) => {
                const movieCard = document.createElement('div');
                movieCard.className = 'movie-card group aspect-[2/3] rounded-xl shadow-lg card-enter-animation';
                movieCard.dataset.movieId = movie.id;
                movieCard.dataset.listName = currentStatus;
                movieCard.style.animationDelay = `${index * 50}ms`;
                const poster = movie.posters && movie.posters.length > 0 ? movie.posters[0] : 'https://placehold.co/400x600/1c1917/57534e?text=无海报';
                movieCard.innerHTML = `
                    <button class="delete-btn absolute top-2 right-2 z-20 w-8 h-8 flex items-center justify-center bg-black/50 rounded-full text-white hover:bg-red-600/80 transition-colors" title="删除电影">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                    </button>
                    <a href="/movie/${currentStatus}/${movie.id}" class="block w-full h-full">
                        <div class="poster-image-wrapper w-full h-full rounded-xl overflow-hidden">
                            <img src="${poster}" alt="${movie.title}" class="w-full h-full object-cover" onerror="this.onerror=null;this.src='https://placehold.co/400x600/1c1917/57534e?text=图片丢失';">
                        </div>
                        <div class="movie-info absolute bottom-0 left-0 right-0 p-4 rounded-b-xl crystal-glass">
                            <h3 class="font-bold text-white truncate">${movie.title} (${movie.year})</h3>
                            <p class="text-xs text-gray-300 truncate">导演: ${movie.director}</p>
                            <p class="text-xs text-gray-400 truncate mt-1">主演: ${movie.actors_string}</p>
                        </div>
                    </a>
                `;
                dom.movieWall.appendChild(movieCard);
            });
            updateInspirationBtn();
        }

        function renderCollageView() {
            dom.movieWall.innerHTML = '';
            const watchedImages = (movieLists.watched || []).flatMap(m => 
                [...(m.posters || []), ...(m.stills || [])].map(imgUrl => ({ src: imgUrl, title: m.title }))
            );
            if (watchedImages.length === 0) {
                dom.movieWall.innerHTML = `<p class="text-stone-400 text-center">“已看”列表里没有图片来制作拼接效果。</p>`;
                return;
            }
            for (let i = watchedImages.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [watchedImages[i], watchedImages[j]] = [watchedImages[j], watchedImages[i]];
            }
            const selectedImages = watchedImages.slice(0, Math.min(300, watchedImages.length));

            selectedImages.forEach((img, index) => {
                const item = document.createElement('div');
                item.className = 'collage-item card-enter-animation';
                item.style.animationDelay = `${index * 15}ms`;
                item.innerHTML = `
                    <img src="${img.src}" loading="lazy" onerror="this.parentElement.style.display='none'">
                    <div class="collage-info"><h3 class="text-xs font-bold truncate">${img.title}</h3></div>
                `;
                dom.movieWall.appendChild(item);
            });
        }

        function renderSearchResults(results) {
            dom.searchResultsContainer.innerHTML = '';
            if (results.length === 0) {
                dom.searchResultsContainer.innerHTML = '<p class="text-stone-400 text-center p-4">未找到相关结果。</p>';
            } else {
                results.forEach(movie => {
                    const item = document.createElement('div');
                    item.className = 'search-modal-item flex items-center gap-4 p-3 rounded-lg transition';
                    const posterUrl = movie.poster_path ? `${TMDB_IMAGE_BASE_URL_JS}${movie.poster_path}` : 'https://placehold.co/100x150/1c1917/57534e?text=N/A';
                    item.innerHTML = `
                        <img src="${posterUrl}" class="w-16 rounded-md" alt="poster">
                        <div class="flex-grow">
                            <h3 class="font-bold text-white">${movie.title} (${movie.year || 'N/A'})</h3>
                            <p class="text-sm text-stone-400 line-clamp-2">${movie.overview}</p>
                        </div>
                        <div class="flex flex-col gap-2">
                            <button data-list="wantToWatch" data-tmdb-id="${movie.tmdb_id}" data-media-type="${movie.media_type}" class="add-btn text-xs px-2 py-1 rounded-md bg-sky-800/50 hover:bg-sky-700/50">想看</button>
                            <button data-list="watching" data-tmdb-id="${movie.tmdb_id}" data-media-type="${movie.media_type}" class="add-btn text-xs px-2 py-1 rounded-md bg-amber-800/50 hover:bg-amber-700/50">在看</button>
                            <button data-list="watched" data-tmdb-id="${movie.tmdb_id}" data-media-type="${movie.media_type}" class="add-btn text-xs px-2 py-1 rounded-md bg-emerald-800/50 hover:bg-emerald-700/50">已看</button>
                        </div>
                    `;
                    dom.searchResultsContainer.appendChild(item);
                });
            }
            dom.searchModal.classList.remove('hidden');
        }

        function updateDynamicBackground() {
            const allStills = Object.values(movieLists).flat().flatMap(m => (m.stills && m.stills.length > 0 ? m.stills : m.posters) || []);
            if (allStills.length === 0) return;
            const randomStill = allStills[Math.floor(Math.random() * allStills.length)];
            if (!randomStill) return;
            const newBg = document.createElement('div');
            newBg.className = 'background-image';
            newBg.style.backgroundImage = `url('${randomStill}')`;
            newBg.style.opacity = '0';
            dom.backgroundContainer.appendChild(newBg);
            setTimeout(() => { newBg.style.opacity = '1'; }, 100);
            if (dom.backgroundContainer.children.length > 1) {
                setTimeout(() => dom.backgroundContainer.removeChild(dom.backgroundContainer.children[0]), 1500);
            }
        }
        
        function closeSearchModal() { dom.searchModal.classList.add('hidden'); }
        function updateActiveTab(target) {
            dom.tabs.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active', 'text-white');
                btn.classList.add('text-stone-400');
            });
            target.classList.add('active', 'text-white');
            target.classList.remove('text-stone-400');
        }
        function updateInspirationBtn() { dom.inspirationBtn.disabled = !movieLists.wantToWatch || movieLists.wantToWatch.length === 0; }
        function resetSpotlight() { document.querySelectorAll('.movie-card').forEach(c => c.classList.remove('spotlight', 'dimmed')); }

        // --- EVENT LISTENERS ---
        function setupEventListeners() {
            dom.fileUpload.addEventListener('change', handleFileUpload);
            dom.searchBtn.addEventListener('click', handleSearch);
            dom.searchInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleSearch(); });
            dom.closeSearchModalBtn.addEventListener('click', closeSearchModal);
            dom.searchModal.addEventListener('click', (e) => { if (e.target.id === 'searchModal') closeSearchModal(); });
            dom.searchResultsContainer.addEventListener('click', handleAddMovie);

            dom.tabs.addEventListener('click', (e) => {
                const target = e.target.closest('.tab-btn');
                if (target) {
                    currentStatus = target.dataset.status;
                    currentView = 'grid';
                    updateActiveTab(target);
                    render();
                    dom.viewToggleBtn.disabled = currentStatus !== 'watched';
                    dom.gridIcon.classList.remove('hidden');
                    dom.collageIcon.classList.add('hidden');
                }
            });

            dom.viewToggleBtn.addEventListener('click', () => {
                if (dom.viewToggleBtn.disabled) return;
                currentView = currentView === 'grid' ? 'collage' : 'grid';
                dom.gridIcon.classList.toggle('hidden', currentView === 'collage');
                dom.collageIcon.classList.toggle('hidden', currentView === 'grid');
                render();
            });

            dom.movieWall.addEventListener('click', (e) => {
                const deleteBtn = e.target.closest('.delete-btn');
                if (deleteBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const card = e.target.closest('.movie-card');
                    const movieId = card.dataset.movieId;
                    const listName = card.dataset.listName;
                    dom.confirmDeleteModal.classList.remove('hidden');
                    dom.confirmDeleteBtn.onclick = () => {
                        deleteMovie(listName, movieId);
                        dom.confirmDeleteModal.classList.add('hidden');
                    };
                }
            });
            
            dom.cancelDeleteBtn.addEventListener('click', () => dom.confirmDeleteModal.classList.add('hidden'));
            
            dom.movieWall.addEventListener('mousemove', (e) => {
                if (currentView === 'collage') return;
                const card = e.target.closest('.movie-card');
                if(card){
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left, y = e.clientY - rect.top;
                    const { width, height } = rect;
                    const rotateX = (y / height - 0.5) * -20;
                    const rotateY = (x / width - 0.5) * 20;
                    card.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
                }
            });
            dom.movieWall.addEventListener('mouseleave', () => document.querySelectorAll('.movie-card').forEach(card => card.style.transform = ''));

            dom.inspirationBtn.addEventListener('click', () => {
                if (dom.inspirationBtn.disabled) return;
                resetSpotlight();
                const wantToWatchList = movieLists.wantToWatch;
                if (!wantToWatchList || wantToWatchList.length === 0) return;
                const randomMovie = wantToWatchList[Math.floor(Math.random() * wantToWatchList.length)];
                if (currentStatus !== 'wantToWatch') {
                    currentStatus = 'wantToWatch';
                    updateActiveTab(dom.tabs.querySelector('.tab-btn[data-status="wantToWatch"]'));
                    render();
                }
                setTimeout(() => {
                    const targetCard = document.querySelector(`.movie-card[data-movie-id="${randomMovie.id}"]`);
                    if (targetCard) {
                        dom.movieWall.querySelectorAll('.movie-card').forEach(card => card.classList.add('dimmed'));
                        targetCard.classList.remove('dimmed');
                        targetCard.classList.add('spotlight');
                        targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }, 100);
            });

            document.body.addEventListener('click', (e) => { if (!e.target.closest('.movie-card') && !e.target.closest('#inspirationBtn')) resetSpotlight(); });
            
            // Settings Modal Listeners
            dom.settingsBtn.addEventListener('click', () => dom.settingsModal.classList.remove('hidden'));
            dom.closeSettingsBtn.addEventListener('click', () => dom.settingsModal.classList.add('hidden'));
            dom.settingsModal.addEventListener('click', (e) => { if (e.target.id === 'settingsModal') dom.settingsModal.classList.add('hidden'); });
            
            dom.taglineLangSelect.addEventListener('change', (e) => localStorage.setItem('taglineLang', e.target.value));
            dom.posterLangSelect.addEventListener('change', (e) => localStorage.setItem('posterLang', e.target.value));
            
            dom.clearCacheBtn.addEventListener('click', async () => {
                if (confirm('你真的要删除所有电影数据吗？这个操作无法撤销！')) {
                    try {
                        const response = await fetch('/api/clear_cache', { method: 'POST' });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.detail);
                        setStatus(result.message, 4000);
                        movieLists = { watched: [], watching: [], wantToWatch: [] };
                        render();
                        dom.settingsModal.classList.add('hidden');
                    } catch(error) {
                        setStatus(`清除失败: ${error.message}`);
                    }
                }
            });
        }
        
        // --- INITIALIZATION ---
        function init() {
            // Load settings from localStorage
            dom.taglineLangSelect.value = localStorage.getItem('taglineLang') || 'zh-CN';
            dom.posterLangSelect.value = localStorage.getItem('posterLang') || 'zh,en,null';
            
            setupEventListeners();
            fetchMovieData();
            updateActiveTab(dom.tabs.querySelector('.tab-btn.active'));
            dom.viewToggleBtn.disabled = currentStatus !== 'watched';
        }
        
        init();
    </script>
</body>
</html>
"""

# 电影详情页
HTML_MOVIE_DETAIL_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电影详情</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #000; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.3); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.5); }
        .crystal-glass { background: rgba(18, 18, 18, 0.6); backdrop-filter: blur(40px) saturate(150%); -webkit-backdrop-filter: blur(40px) saturate(150%); border: 1px solid rgba(255, 255, 255, 0.1); }
        .gallery-item.hidden { display: none; }
        #lightbox { transition: opacity 0.3s ease-in-out; }
        #lightbox-img { transition: transform 0.3s ease-in-out; max-width: 90vw; max-height: 85vh; }
    </style>
</head>
<body class="text-gray-300 antialiased">
    <div id="loading" class="fixed inset-0 bg-black flex items-center justify-center z-50 text-white">加载中...</div>
    
    <div id="app-container" class="min-h-screen bg-black text-white relative overflow-hidden hidden">
        <div id="background-image" class="absolute inset-0 bg-cover bg-center" style="filter: blur(24px) brightness(0.5);"></div>
        
        <a href="/movies" class="absolute top-4 left-4 z-20 crystal-glass text-white w-11 h-11 rounded-full flex items-center justify-center hover:bg-stone-700/80 transition" title="返回电影墙">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </a>

        <div class="relative z-10 p-4 md:p-8 max-w-6xl mx-auto lg:grid lg:grid-cols-3 lg:gap-12 items-start">
            <!-- Left Column: Poster -->
            <div class="lg:col-span-1 lg:sticky lg:top-8 text-center">
                <div class="relative mx-auto w-64 lg:w-full">
                    <div class="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl overflow-hidden shadow-lg">
                        <img id="movie-poster" src="" alt="poster" class="w-full rounded-2xl aspect-[2/3] object-cover"/>
                    </div>
                </div>
            </div>

            <!-- Right Column: Details -->
            <div class="lg:col-span-2 space-y-8 mt-6 lg:mt-0">
                <div class="space-y-4">
                    <h1 id="movie-title" class="text-4xl lg:text-5xl font-bold drop-shadow-lg"></h1>
                    <p id="movie-tagline" class="text-lg text-amber-100 opacity-80 italic hidden"></p>
                    <div class="flex items-center flex-wrap gap-x-6 gap-y-2 text-base opacity-80">
                        <span id="movie-year" class="flex items-center gap-1.5"></span>
                        <span id="movie-rating" class="flex items-center gap-1.5"></span>
                    </div>
                     <div class="flex items-center flex-wrap gap-x-6 gap-y-2 text-sm opacity-70 pt-2">
                        <span id="movie-budget"></span>
                        <span id="movie-revenue"></span>
                    </div>
                </div>
                
                <div class="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6 space-y-3">
                    <h2 class="text-xl font-semibold">剧情简介</h2>
                    <p id="movie-overview" class="text-base leading-relaxed opacity-90"></p>
                </div>

                <div class="space-y-4">
                    <h2 class="text-xl font-semibold">演职员</h2>
                    <div id="movie-cast" class="flex gap-4 overflow-x-auto pb-2"></div>
                </div>

                <div class="space-y-4">
                    <h2 class="text-xl font-semibold">海报 & 剧照</h2>
                    <div id="gallery" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"></div>
                    <button id="gallery-toggle" class="text-amber-400 hover:text-amber-300 transition hidden mt-2">显示全部</button>
                </div>

                 <div class="space-y-4">
                    <h2 class="text-xl font-semibold">相关推荐</h2>
                    <div id="movie-recommendations" class="flex gap-4 overflow-x-auto pb-2"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Lightbox Modal -->
    <div id="lightbox" class="fixed inset-0 bg-black/90 z-50 flex items-center justify-center hidden opacity-0">
        <img id="lightbox-img" src="" class="rounded-lg shadow-2xl" alt="放大的图片">
        <button id="lightbox-close" class="absolute top-5 right-5 text-white text-4xl font-bold">&times;</button>
        <button id="lightbox-prev" class="absolute left-5 top-1/2 -translate-y-1/2 text-white text-3xl p-3 rounded-full bg-white/10 hover:bg-white/20 transition-all">&lt;</button>
        <button id="lightbox-next" class="absolute right-5 top-1/2 -translate-y-1/2 text-white text-3xl p-3 rounded-full bg-white/10 hover:bg-white/20 transition-all">&gt;</button>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', async () => {
            const dom = {
                loading: document.getElementById('loading'),
                appContainer: document.getElementById('app-container'),
                bgImage: document.getElementById('background-image'),
                poster: document.getElementById('movie-poster'),
                title: document.getElementById('movie-title'),
                tagline: document.getElementById('movie-tagline'),
                year: document.getElementById('movie-year'),
                rating: document.getElementById('movie-rating'),
                budget: document.getElementById('movie-budget'),
                revenue: document.getElementById('movie-revenue'),
                overview: document.getElementById('movie-overview'),
                cast: document.getElementById('movie-cast'),
                gallery: document.getElementById('gallery'),
                galleryToggle: document.getElementById('gallery-toggle'),
                recommendations: document.getElementById('movie-recommendations'),
                lightbox: document.getElementById('lightbox'),
                lightboxImg: document.getElementById('lightbox-img'),
                lightboxClose: document.getElementById('lightbox-close'),
                lightboxPrev: document.getElementById('lightbox-prev'),
                lightboxNext: document.getElementById('lightbox-next'),
            };

            const pathParts = window.location.pathname.split('/');
            const source = pathParts[2]; // Can be 'tmdb' or a list name like 'watched'
            const id = pathParts[3];
            
            let allImages = [];
            let currentImageIndex = 0;

            if (!source || !id) {
                showError('错误：无效的电影链接。');
                return;
            }

            try {
                // Determine which API endpoint to call based on the URL
                const apiUrl = source === 'tmdb'
                    ? `/api/tmdb_data/${pathParts[3]}/${pathParts[4]}` // URL is /movie/tmdb/movie/12345
                    : `/api/movie_data/${source}/${id}`; // URL is /movie/watched/watched-0

                const response = await fetch(apiUrl);
                if (!response.ok) throw new Error('无法获取电影数据');
                const movie = await response.json();
                renderAll(movie);
            } catch (error) {
                console.error('加载详情页失败:', error);
                showError('加载电影详情失败。请返回重试。');
            } finally {
                dom.loading.classList.add('hidden');
                dom.appContainer.classList.remove('hidden');
            }

            function showError(message) {
                dom.appContainer.innerHTML = `<div class="text-center p-8 text-red-400">${message}</div>`;
            }
            
            function formatCurrency(num) {
                if (num > 0) return `$${num.toLocaleString()}`;
                return '未公开';
            }

            function renderAll(movie) {
                const posterUrl = movie.posters && movie.posters.length > 0 ? movie.posters[0] : 'https://placehold.co/500x750/334155/ffffff?text=No+Poster';
                const backgroundUrl = (movie.stills && movie.stills.length > 0 ? movie.stills[0] : posterUrl);

                dom.bgImage.style.backgroundImage = `url('${backgroundUrl}')`;
                dom.poster.src = posterUrl;
                dom.title.textContent = movie.title || '未知标题';

                const taglineLang = localStorage.getItem('taglineLang') || 'zh-CN';
                const taglineToShow = (taglineLang === 'en-US' && movie.tagline_en) ? movie.tagline_en : movie.tagline;

                if (taglineToShow) {
                    dom.tagline.textContent = taglineToShow;
                    dom.tagline.classList.remove('hidden');
                } else {
                    dom.tagline.classList.add('hidden');
                }

                dom.year.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-5 h-5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span>${movie.year || 'N/A'}</span>`;
                
                if(movie.rating > 0) {
                    dom.rating.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5 text-yellow-400"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg><span>${movie.rating.toFixed(1)}</span>`;
                }
                dom.budget.innerHTML = `<strong>预算:</strong> ${formatCurrency(movie.budget)}`;
                dom.revenue.innerHTML = `<strong>票房:</strong> ${formatCurrency(movie.revenue)}`;
                dom.overview.textContent = movie.plot || '暂无简介。';

                renderCast(movie.actors || []);
                renderGallery(movie.posters || [], movie.stills || []);
                renderRecommendations(movie.recommendations || []);
            }
            
            function renderCast(actors) {
                dom.cast.innerHTML = '';
                if (actors.length === 0) {
                    dom.cast.innerHTML = '<p class="text-stone-400">暂无主演信息</p>';
                    return;
                }
                actors.forEach(actor => {
                    const profileUrl = actor.profile_path ? `https://image.tmdb.org/t/p/w200${actor.profile_path}` : 'https://placehold.co/200x300/1c1917/57534e?text=N/A';
                    dom.cast.innerHTML += `
                        <div class="flex-shrink-0 text-center w-24">
                            <img src="${profileUrl}" alt="${actor.name}" class="w-20 h-20 rounded-full border-2 border-white/30 object-cover mx-auto shadow-lg"/>
                            <p class="text-sm mt-2 font-medium truncate">${actor.name}</p>
                            <p class="text-xs text-white/60 truncate">${actor.character}</p>
                        </div>
                    `;
                });
            }

            function renderGallery(posters, stills) {
                allImages = [...new Set([...posters, ...stills])];
                dom.gallery.innerHTML = '';
                if (allImages.length === 0) {
                    dom.gallery.innerHTML = '<p class="text-stone-400">暂无海报或剧照</p>';
                    return;
                }
                
                allImages.forEach((imgUrl, index) => {
                    const isHidden = index >= 8 ? 'hidden' : '';
                    dom.gallery.innerHTML += `
                        <div data-index="${index}" class="gallery-item ${isHidden} block rounded-lg overflow-hidden aspect-video transform hover:scale-105 transition-transform duration-300 cursor-pointer">
                            <img src="${imgUrl}" loading="lazy" class="w-full h-full object-cover" onerror="this.parentElement.style.display='none'">
                        </div>
                    `;
                });

                if (allImages.length > 8) {
                    dom.galleryToggle.classList.remove('hidden');
                }

                dom.galleryToggle.addEventListener('click', () => {
                    dom.gallery.querySelectorAll('.gallery-item.hidden').forEach(item => item.classList.remove('hidden'));
                    dom.galleryToggle.classList.add('hidden');
                });
                
                dom.gallery.addEventListener('click', (e) => {
                    const item = e.target.closest('.gallery-item');
                    if (item) {
                        openLightbox(parseInt(item.dataset.index));
                    }
                });
            }

            function renderRecommendations(recs) {
                dom.recommendations.innerHTML = '';
                if (recs.length === 0) {
                    dom.recommendations.parentElement.classList.add('hidden');
                    return;
                }
                recs.forEach(rec => {
                    const posterUrl = rec.poster_path ? `https://image.tmdb.org/t/p/w300${rec.poster_path}` : 'https://placehold.co/300x450/1c1917/57534e?text=N/A';
                    // **FIX**: Link to our own detail page for recommendations
                    const detailUrl = `/movie/tmdb/${rec.media_type}/${rec.id}`;
                    dom.recommendations.innerHTML += `
                        <a href="${detailUrl}" class="block bg-white/10 backdrop-blur-xl border border-white/20 rounded-xl overflow-hidden flex-shrink-0 w-36 lg:w-40 transform hover:-translate-y-2 transition-transform duration-300">
                            <img src="${posterUrl}" alt="${rec.title}" class="w-full h-52 lg:h-60 object-cover"/>
                            <p class="text-xs p-2 font-medium truncate">${rec.title}</p>
                        </a>
                    `;
                });
            }

            function openLightbox(index) {
                currentImageIndex = index;
                updateLightboxImage();
                dom.lightbox.classList.remove('hidden');
                setTimeout(() => dom.lightbox.classList.add('opacity-100'), 10);
            }

            function closeLightbox() {
                dom.lightbox.classList.remove('opacity-100');
                setTimeout(() => dom.lightbox.classList.add('hidden'), 300);
            }

            function updateLightboxImage() {
                dom.lightboxImg.src = allImages[currentImageIndex];
                dom.lightboxPrev.style.display = currentImageIndex > 0 ? 'block' : 'none';
                dom.lightboxNext.style.display = currentImageIndex < allImages.length - 1 ? 'block' : 'none';
            }

            dom.lightboxClose.addEventListener('click', closeLightbox);
            dom.lightbox.addEventListener('click', (e) => { if (e.target.id === 'lightbox') closeLightbox(); });
            dom.lightboxPrev.addEventListener('click', () => { if(currentImageIndex > 0) { currentImageIndex--; updateLightboxImage(); } });
            dom.lightboxNext.addEventListener('click', () => { if(currentImageIndex < allImages.length - 1) { currentImageIndex++; updateLightboxImage(); } });
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# --- TMDB 辅助函数 ---
# ==============================================================================
def get_enriched_tmdb_details(tmdb_id: int, media_type: str, poster_lang: str):
    """获取一个电影的完整中英文信息并合并。"""
    # Fetch Chinese data (primary)
    details_zh = get_tmdb_details(tmdb_id, media_type, 'zh-CN', poster_lang)
    if not details_zh:
        return None
    
    # Fetch English data (for tagline)
    details_en = get_tmdb_details(tmdb_id, media_type, 'en-US', poster_lang)
    
    # Merge data
    details_zh['tagline_en'] = details_en.get('tagline', '') if details_en else ''
    
    return details_zh

def convert_excel_to_json(excel_path, json_path, poster_lang):
    """从Excel文件转换数据到JSON格式, 并用TMDB数据进行丰富。"""
    try:
        xls = pd.ExcelFile(excel_path)
    except Exception as e:
        print(f"读取Excel文件时发生错误: {e}")
        return False

    all_data = {"watched": [], "watching": [], "wantToWatch": []}
    sheet_map = {'看过的电影': 'watched', '在看的电影': 'watching', '想看的电影': 'wantToWatch'}
    
    existing_tmdb_ids = {}
    if os.path.exists(json_path):
        with file_lock:
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    all_data = json.load(f)
                    for status, movies in all_data.items():
                        for movie in movies:
                            tmdb_id_str = movie.get('id', '').split('-')[-1]
                            if tmdb_id_str.isdigit():
                                existing_tmdb_ids[int(tmdb_id_str)] = True
                except json.JSONDecodeError:
                    pass

    for sheet_name, status_key in sheet_map.items():
        if sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name).fillna('')
                records = df.to_dict('records')
                print(f"\n--- Processing sheet: {sheet_name} ---")
                for record in records:
                    title = record.get('标题')
                    year = str(record.get('年份', ''))
                    if not title:
                        continue

                    print(f"Processing '{title}' ({year})...")
                    search_results = search_tmdb(title, year)
                    
                    if search_results:
                        top_result = search_results[0]
                        tmdb_id = top_result['tmdb_id']
                        media_type = top_result['media_type']
                        
                        if tmdb_id in existing_tmdb_ids:
                            print(f"  -> Skipping '{title}', as TMDB ID {tmdb_id} already exists in the lists.")
                            continue

                        details = get_enriched_tmdb_details(tmdb_id, media_type, poster_lang)
                        if details:
                            movie_object = format_tmdb_details_to_movie_object(details, media_type, f"{status_key}-{tmdb_id}")
                            if not movie_object['posters']:
                                movie_object['posters'] = [p for p in str(record.get('海报链接', '')).split() if p.startswith('http')]
                            if not movie_object['stills']:
                                movie_object['stills'] = [s for s in str(record.get('剧照链接', '')).split() if s.startswith('http')]
                            
                            all_data[status_key].insert(0, movie_object)
                            existing_tmdb_ids[tmdb_id] = True
                            print(f"  -> Success: Found and added '{title}' with TMDB ID {tmdb_id}.")
                        else:
                            print(f"  -> Warning: Could not fetch details for TMDB ID {tmdb_id}.")
                    else:
                        print(f"  -> Warning: Could not find '{title}' ({year}) on TMDB. Skipping.")
                    time.sleep(0.5)
            except Exception as e:
                print(f"处理Sheet '{sheet_name}' 时出错: {e}")
    
    try:
        with file_lock:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"\n成功将数据转换并保存到 {json_path}")
        return True
    except Exception as e:
        print(f"写入JSON文件时出错: {e}")
        return False

def search_tmdb(query: str, year: str = None):
    """使用TMDB API搜索电影和剧集。"""
    search_url = f"{TMDB_API_BASE_URL}/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'zh-CN', 'include_adult': False}
    if year:
        params['primary_release_year'] = year
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get('results', [])
        formatted_results = []
        for item in results:
            media_type = item.get('media_type')
            if media_type not in ['movie', 'tv']: continue
            title = item.get('title') or item.get('name', '未知标题')
            release_year = (item.get('release_date') or item.get('first_air_date', ''))[:4]
            formatted_results.append({
                'tmdb_id': item.get('id'), 'media_type': media_type, 'title': title, 'year': release_year,
                'overview': item.get('overview', ''), 'poster_path': item.get('poster_path')
            })
        return formatted_results
    except requests.RequestException as e:
        print(f"Error searching TMDB: {e}")
        return None

def get_tmdb_details(tmdb_id: int, media_type: str, lang: str, poster_lang: str):
    """获取指定ID的电影或剧集的详细信息, 包含推荐。"""
    details_url = f"{TMDB_API_BASE_URL}/{media_type}/{tmdb_id}"
    params = {
        'api_key': TMDB_API_KEY, 'language': lang,
        'append_to_response': 'credits,images,recommendations',
        'include_image_language': poster_lang
    }
    try:
        response = requests.get(details_url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting TMDB details for lang {lang}: {e}")
        return None

def format_tmdb_details_to_movie_object(details, media_type, movie_id=None):
    """将TMDB的详细信息格式化为我们应用内部的电影对象结构。"""
    if not details:
        return None
    
    title = details.get('title') or details.get('name', '未知标题')
    year = (details.get('release_date') or details.get('first_air_date', ''))[:4]
    directors_list = [c['name'] for c in details.get('credits', {}).get('crew', []) if c['job'] == 'Director']
    actors_list = [{'name': c['name'], 'character': c.get('character', ''), 'profile_path': c.get('profile_path')} for c in details.get('credits', {}).get('cast', [])[:10]]
    
    recommendations_list = []
    for r in details.get('recommendations', {}).get('results', [])[:10]:
        rec_media_type = r.get('media_type', media_type)
        recommendations_list.append({'id': r.get('id'), 'title': r.get('title') or r.get('name'), 'poster_path': r.get('poster_path'), 'media_type': rec_media_type})

    posters = [f"{TMDB_IMAGE_BASE_URL}{p['file_path']}" for p in details.get('images', {}).get('posters', [])]
    stills = [f"{TMDB_IMAGE_BASE_URL}{b['file_path']}" for b in details.get('images', {}).get('backdrops', [])]
    
    return {
        'id': movie_id or f"tmdb-{details.get('id')}",
        'media_type': media_type,
        'title': title, 'year': year, 'director': ', '.join(directors_list), 
        'actors_string': ', '.join([a['name'] for a in actors_list]),
        'actors': actors_list,
        'plot': details.get('overview', '暂无简介'),
        'tagline': details.get('tagline', ''),
        'tagline_en': details.get('tagline_en', ''),
        'posters': posters, 'stills': stills,
        'rating': details.get('vote_average', 0),
        'budget': details.get('budget', 0),
        'revenue': details.get('revenue', 0),
        'recommendations': recommendations_list
    }

# ==============================================================================
# --- 启动时任务 (STARTUP TASKS) ---
# ==============================================================================
with app.app_context():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # 初始化数据文件（如果不存在）
    if not os.path.exists(HUB_DATA_FILE): 
        with open(HUB_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(CHAT_LOG_FILE): 
        with open(CHAT_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    if not os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, 'w', encoding='utf-8') as f:
            json.dump({"watched": [], "watching": [], "wantToWatch": []}, f, ensure_ascii=False, indent=2)
    print("服务器启动，所有目录和数据文件已准备就绪。")

# ==============================================================================
# --- 页面路由 (HTML PAGE ROUTES) ---
# ==============================================================================
@app.route('/')
def home():
    return HTML_CONTENT

@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route('/movies')
def movies_page():
    return HTML_MOVIES_PAGE

@app.route('/movie/<path:path>')
def movie_detail_page(path):
    return HTML_MOVIE_DETAIL_PAGE

# ==============================================================================
# --- HUB & CHAT API 端点 ---
# ==============================================================================
@app.route('/load_data', methods=['GET'])
def load_hub_data():
    if not os.path.exists(HUB_DATA_FILE): return jsonify({})
    with open(HUB_DATA_FILE, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))

@app.route('/save_data', methods=['POST'])
def save_hub_data():
    with open(HUB_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(request.json, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "success"})

@app.route('/save_chat', methods=['POST'])
def save_chat():
    logs = []
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, 'r', encoding='utf-8') as f: logs = json.load(f)
        except json.JSONDecodeError: pass
    logs.append({"role": request.json.get('role'), "content": request.json.get('content'), "timestamp": datetime.utcnow().isoformat()})
    with open(CHAT_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "ok"})

@app.route('/load_chat', methods=['GET'])
def load_chat():
    if not os.path.exists(CHAT_LOG_FILE): return jsonify([])
    with open(CHAT_LOG_FILE, 'r', encoding='utf-8') as f:
        try: return jsonify(json.load(f))
        except json.JSONDecodeError: return jsonify([])

@app.route('/api/chat', methods=['POST'])
def chat_proxy():
    try:
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {AI_API_KEY}'}
        payload = {'model': AI_MODEL_NAME, 'messages': request.json.get('messages')}
        response = requests.post(AI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        return jsonify({"error": {"message": f"AI服务连接失败: {e}"}}), 502
    except Exception as e:
        return jsonify({"error": {"message": f"服务器内部错误: {e}"}}), 500

# ==============================================================================
# --- MOVIE API 端点 ---
# ==============================================================================
@app.route('/api/movies', methods=['GET'])
def get_movies():
    if not os.path.exists(CACHE_JSON):
        return jsonify({"watched": [], "watching": [], "wantToWatch": []}), HTTPStatus.NOT_FOUND, {"X-Error": "Cache file not found. Please upload an Excel file first."}
    try:
        with file_lock:
            with open(CACHE_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"detail": f"Error reading cache file: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR

@app.route('/api/movie_data/<list_name>/<movie_id>', methods=['GET'])
def get_single_movie_data(list_name, movie_id):
    poster_lang = request.args.get('posterLang', 'zh,en,null')
    try:
        with file_lock:
            with open(CACHE_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        movie = next((m for m in data.get(list_name, []) if m.get('id') == movie_id), None)
        if not movie:
            return jsonify({"detail": "Movie not found"}), HTTPStatus.NOT_FOUND

        tmdb_id_str = movie.get('id', '').split('-')[-1]
        media_type = movie.get('media_type')
        
        if not (tmdb_id_str.isdigit() and media_type):
            search_results = search_tmdb(movie.get('title'), movie.get('year'))
            if not search_results:
                return jsonify(movie) # Return basic data if not found
            top_result = search_results[0]
            media_type = top_result['media_type']
            tmdb_id_str = str(top_result['tmdb_id'])
        
        details = get_enriched_tmdb_details(int(tmdb_id_str), media_type, poster_lang)
        if details:
            enriched_movie = format_tmdb_details_to_movie_object(details, media_type, movie_id)
            if not enriched_movie['posters']: enriched_movie['posters'] = movie.get('posters', [])
            if not enriched_movie['stills']: enriched_movie['stills'] = movie.get('stills', [])
            return jsonify(enriched_movie)
        
        return jsonify(movie)
    except Exception as e:
        print(f"Error in get_single_movie_data: {e}")
        return jsonify({"detail": f"Error processing request: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR

@app.route('/api/tmdb_data/<media_type>/<int:tmdb_id>', methods=['GET'])
def get_tmdb_movie_data(media_type, tmdb_id):
    poster_lang = request.args.get('posterLang', 'zh,en,null')
    details = get_enriched_tmdb_details(tmdb_id, media_type, poster_lang)
    if details:
        return jsonify(format_tmdb_details_to_movie_object(details, media_type))
    return jsonify({"detail": "Failed to fetch data from TMDB"}), HTTPStatus.NOT_FOUND

@app.route('/api/upload', methods=['POST'])
def upload_file():
    poster_lang = request.form.get('posterLang', 'zh,en,null')
    if 'file' not in request.files:
        return jsonify({"detail": "No file part"}), HTTPStatus.BAD_REQUEST
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.xlsx'):
        return jsonify({"detail": "Invalid file"}), HTTPStatus.BAD_REQUEST
    
    source_excel_path = os.path.join(UPLOAD_DIR, SOURCE_EXCEL_NAME)
    try:
        file.save(source_excel_path)
        success = convert_excel_to_json(source_excel_path, CACHE_JSON, poster_lang)
        if success:
            return jsonify({"message": f"文件 '{file.filename}' 上传成功并已处理。"})
        else:
            return jsonify({"detail": "文件处理失败，请检查服务器日志。"}), HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as e:
        return jsonify({"detail": f"An error occurred during upload: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR

@app.route('/api/search', methods=['GET'])
def search_movies_endpoint():
    query = request.args.get('query')
    if not query:
        return jsonify({"detail": "Query is required."}), HTTPStatus.BAD_REQUEST
    results = search_tmdb(query)
    return jsonify(results) if results is not None else (jsonify({"detail": "Failed to fetch from TMDB."}), HTTPStatus.SERVICE_UNAVAILABLE)

@app.route('/api/add', methods=['POST'])
def add_movie_to_list():
    req = request.get_json()
    poster_lang = req.get('posterLang', 'zh,en,null')
    if not req or 'tmdb_id' not in req or 'media_type' not in req or 'target_list' not in req:
        return jsonify({"detail": "Invalid JSON"}), HTTPStatus.BAD_REQUEST

    details = get_enriched_tmdb_details(req['tmdb_id'], req['media_type'], poster_lang)
    if not details:
        return jsonify({"detail": "Failed to fetch from TMDB."}), HTTPStatus.SERVICE_UNAVAILABLE

    new_movie = format_tmdb_details_to_movie_object(details, req['media_type'], f"{req['target_list']}-{req['tmdb_id']}")

    with file_lock:
        data = {"watched": [], "watching": [], "wantToWatch": []}
        if os.path.exists(CACHE_JSON):
            try:
                with open(CACHE_JSON, 'r', encoding='utf-8') as f: data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError): pass

        if any(movie.get('id', '').split('-')[-1] == str(req['tmdb_id']) for lst in data.values() for movie in lst):
            return jsonify({"detail": f"'{new_movie['title']}' 已存在于列表中。"}), HTTPStatus.CONFLICT
        
        data[req['target_list']].insert(0, new_movie)
        
        try:
            with open(CACHE_JSON, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            return jsonify({"detail": f"Error writing to cache: {e}"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"message": f"'{new_movie['title']}' 已成功添加。"})

@app.route('/api/delete', methods=['POST'])
def delete_movie():
    req = request.get_json()
    if not req or 'list_name' not in req or 'movie_id' not in req:
        return jsonify({"detail": "Invalid JSON"}), HTTPStatus.BAD_REQUEST
    
    with file_lock:
        if not os.path.exists(CACHE_JSON):
            return jsonify({"detail": "Cache file not found"}), HTTPStatus.NOT_FOUND
        
        with open(CACHE_JSON, 'r', encoding='utf-8') as f: data = json.load(f)
        
        movie_list = data.get(req['list_name'], [])
        original_length = len(movie_list)
        data[req['list_name']] = [m for m in movie_list if m.get('id') != req['movie_id']]
        
        if len(data[req['list_name']]) == original_length:
            return jsonify({"detail": "Movie not found to delete"}), HTTPStatus.NOT_FOUND
            
        with open(CACHE_JSON, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)

    return jsonify({"message": "电影已删除"})

@app.route('/api/clear_cache', methods=['POST'])
def clear_cache():
    with file_lock:
        if os.path.exists(CACHE_JSON):
            os.remove(CACHE_JSON)
    return jsonify({"message": "所有电影数据已清空。"})

# ==============================================================================
# --- 主程序入口 ---
# ==============================================================================
if __name__ == '__main__':
    print("启动 Flask 服务器...")
    print("请在浏览器访问 http://127.0.0.1:7860")
    app.run(host='0.0.0.0', port=7860, debug=True)
