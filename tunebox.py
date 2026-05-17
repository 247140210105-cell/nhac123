"""
Tunebox - Lưu trữ nhạc cá nhân
Chạy: python tunebox.py
Mở trình duyệt: http://localhost:8000
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import uuid
import json

# ── Cấu hình ──────────────────────────────────────────────────────
UPLOAD_DIR = "nhac"
ALLOWED_EXT = {"mp3", "flac", "wav", "ogg", "m4a"}
MAX_SIZE_MB = 50
DB_FILE = "tunebox_songs.json"

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────

def load_songs():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_songs(songs):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)

def fmt_size(size_bytes):
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

# ── App ───────────────────────────────────────────────────────────

app = FastAPI(title="Tunebox")


@app.get("/")
def index():
    return FileResponse("index.html")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = get_ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Định dạng không hỗ trợ. Dùng: {', '.join(ALLOWED_EXT)}")

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(413, f"File quá lớn ({size_mb:.1f}MB). Tối đa {MAX_SIZE_MB}MB")

    song_id = uuid.uuid4().hex[:8]
    filename = f"{song_id}.{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(data)

    title = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename

    songs = load_songs()
    songs.append({
        "id": song_id,
        "title": title,
        "filename": filename,
        "size": len(data),
        "size_fmt": fmt_size(len(data)),
    })
    save_songs(songs)
    return {"ok": True, "id": song_id, "title": title}


@app.get("/api/songs")
def list_songs():
    return load_songs()


@app.get("/api/stream/{song_id}")
def stream(song_id: str):
    songs = load_songs()
    song = next((s for s in songs if s["id"] == song_id), None)
    if not song:
        raise HTTPException(404, "Không tìm thấy bài nhạc")

    path = os.path.join(UPLOAD_DIR, song["filename"])
    if not os.path.exists(path):
        raise HTTPException(404, "File không tồn tại")

    ext = get_ext(song["filename"])
    media_types = {
        "mp3": "audio/mpeg", "flac": "audio/flac",
        "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4"
    }
    media_type = media_types.get(ext, "audio/mpeg")

    def iter_file():
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(iter_file(), media_type=media_type)


@app.delete("/api/songs/{song_id}")
def delete_song(song_id: str):
    songs = load_songs()
    song = next((s for s in songs if s["id"] == song_id), None)
    if not song:
        raise HTTPException(404, "Không tìm thấy")

    path = os.path.join(UPLOAD_DIR, song["filename"])
    if os.path.exists(path):
        os.remove(path)

    save_songs([s for s in songs if s["id"] != song_id])
    return {"ok": True}


if __name__ == "__main__":
    print("🎵 Tunebox đang chạy tại http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
