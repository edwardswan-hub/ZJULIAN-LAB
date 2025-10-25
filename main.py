
import os
import json
import shutil
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from converter import convert_excel_to_json

# --- 配置 ---
UPLOAD_DIR = "uploads"
CACHE_JSON = "movies.json"
SOURCE_EXCEL_NAME = "source.xlsx"
TMDB_API_KEY = "30f8f5d19b6e17b84205bdba71474cd4"
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# --- Pydantic 数据模型 ---
class AddMovieRequest(BaseModel):
    tmdb_id: int
    media_type: str
    target_list: str = Field(..., pattern="^(watched|watching|wantToWatch)$")

# --- FastAPI 应用实例 ---
app = FastAPI()

# --- CORS 跨域配置 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 辅助函数 ---
def search_tmdb(query: str):
    search_url = f"{TMDB_API_BASE_URL}/search/multi"
    params = {'api_key': TMDB_API_KEY, 'query': query, 'language': 'zh-CN', 'include_adult': False}
    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get('results', [])
        formatted_results = []
        for item in results:
            media_type = item.get('media_type')
            if media_type not in ['movie', 'tv']:
                continue
            title = item.get('title') or item.get('name', '未知标题')
            year = (item.get('release_date') or item.get('first_air_date', ''))[:4]
            formatted_results.append({
                'tmdb_id': item.get('id'), 'media_type': media_type, 'title': title, 'year': year,
                'overview': item.get('overview', ''), 'poster_path': item.get('poster_path')
            })
        return formatted_results
    except requests.RequestException as e:
        print(f"Error searching TMDB: {e}")
        return None

def get_tmdb_details(tmdb_id: int, media_type: str):
    details_url = f"{TMDB_API_BASE_URL}/{media_type}/{tmdb_id}"
    params = {
        'api_key': TMDB_API_KEY, 'language': 'zh-CN',
        'append_to_response': 'credits,images',
        'include_image_language': 'zh,en,null'
    }
    try:
        response = requests.get(details_url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting TMDB details: {e}")
        return None

# --- API 端点 ---

@app.on_event("startup")
def on_startup():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    print("服务器启动，上传目录已准备就绪。")
    source_excel_path = os.path.join(UPLOAD_DIR, SOURCE_EXCEL_NAME)
    if os.path.exists(source_excel_path):
        print(f"检测到已存在的源文件 {source_excel_path}，将尝试生成缓存...")
        convert_excel_to_json(source_excel_path, CACHE_JSON)
    else:
        print("未找到源文件，等待上传...")

@app.get("/")
def read_root():
    return {"message": "欢迎来到电影墙API服务！"}

@app.get("/api/movies")
def get_movies():
    if not os.path.exists(CACHE_JSON):
        return JSONResponse(
            content={"watched": [], "watching": [], "wantToWatch": []},
            status_code=404,
            headers={"X-Error": "Cache file not found. Please upload an Excel file first."}
        )
    return FileResponse(CACHE_JSON, media_type='application/json')

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx")):
        raise HTTPException(status_code=400, detail="不合法的文件类型，请上传 .xlsx 文件。")
    source_excel_path = os.path.join(UPLOAD_DIR, SOURCE_EXCEL_NAME)
    try:
        with open(source_excel_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()
    success = convert_excel_to_json(source_excel_path, CACHE_JSON)
    if success:
        return {"message": f"文件 '{file.filename}' 上传成功并已处理。"}
    else:
        raise HTTPException(status_code=500, detail="文件处理失败，请检查服务器日志。")

@app.get("/api/search")
def search_movies_endpoint(query: str = Query(..., min_length=1, max_length=100)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required.")
    results = search_tmdb(query)
    if results is None:
        raise HTTPException(status_code=503, detail="Failed to fetch data from TMDB.")
    return results

@app.post("/api/add")
def add_movie_to_list(request: AddMovieRequest):
    details = get_tmdb_details(request.tmdb_id, request.media_type)
    if not details:
        raise HTTPException(status_code=503, detail="Failed to fetch details from TMDB.")

    # 格式化数据
    title = details.get('title') or details.get('name', '未知标题')
    year = (details.get('release_date') or details.get('first_air_date', ''))[:4]
    directors = ', '.join([c['name'] for c in details.get('credits', {}).get('crew', []) if c['job'] == 'Director'])
    actors = ', '.join([c['name'] for c in details.get('credits', {}).get('cast', [])[:10]])
    posters = [f"{TMDB_IMAGE_BASE_URL}{p['file_path']}" for p in details.get('images', {}).get('posters', [])]
    stills = [f"{TMDB_IMAGE_BASE_URL}{b['file_path']}" for b in details.get('images', {}).get('backdrops', [])]

    new_movie = {
        'id': f"{request.target_list}-{request.tmdb_id}", # 使用tmdb_id确保唯一性
        'title': title, 'year': year, 'director': directors, 'actors': actors,
        'plot': details.get('overview', '暂无简介'),
        'posters': posters, 'stills': stills
    }

    # 读取、更新、写回JSON
    if os.path.exists(CACHE_JSON):
        with open(CACHE_JSON, 'r+', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # 检查是否已存在
                for lst in data.values():
                    if any(movie['id'].split('-')[-1] == str(request.tmdb_id) for movie in lst):
                        raise HTTPException(status_code=409, detail=f"'{title}' 已存在于您的某个列表中。")
                
                data[request.target_list].insert(0, new_movie) # 插入到最前面
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=4)
            except (json.JSONDecodeError, KeyError) as e:
                raise HTTPException(status_code=500, detail=f"Error processing cache file: {e}")
    else: # 如果缓存文件不存在，则创建一个新的
        data = {"watched": [], "watching": [], "wantToWatch": []}
        data[request.target_list].append(new_movie)
        with open(CACHE_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    return {"message": f"'{title}' 已成功添加到 '{request.target_list}' 列表。"}
