"""Публикация Reels через официальный Instagram API (вход через Instagram, без страницы Facebook).
Видео грузится файлом напрямую, хостинг не нужен."""
import os, time
from pathlib import Path
import requests

V = "v21.0"
API = f"https://graph.instagram.com/{V}"

def refresh_token(tok):
    """Продлевает долгоживущий токен ещё на 60 дней (делается при каждом запуске)."""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    return r.json().get("access_token", tok) if r.ok else tok

def publish(video: Path, caption: str) -> str:
    uid = os.environ["IG_USER_ID"]
    tok = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    c = requests.post(f"{API}/{uid}/media", data={"media_type": "REELS", "upload_type": "resumable",
                      "caption": caption, "share_to_feed": "true", "access_token": tok}).json()
    if "id" not in c: raise RuntimeError(c)
    cid, data = c["id"], video.read_bytes()
    r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{V}/{cid}", data=data,
                      headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(data))})
    if not r.ok: raise RuntimeError(r.text)
    for _ in range(60):  # ждём обработку видео
        st = requests.get(f"{API}/{cid}", params={"fields": "status_code", "access_token": tok}).json()
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise RuntimeError(st)
        time.sleep(10)
    p = requests.post(f"{API}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}).json()
    if "id" not in p: raise RuntimeError(p)
    return p["id"]
