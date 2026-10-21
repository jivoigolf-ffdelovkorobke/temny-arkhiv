"""Публикация Reels через официальный Instagram API (вход через Instagram, без страницы Facebook).
API берёт видео по публичной ссылке: workflow кладёт ролик на GitHub Pages этого репозитория.
Запуск: python post_instagram.py <ссылка на mp4> <файл с подписью>"""
import os, sys, time
from pathlib import Path
import requests

API = "https://graph.instagram.com/v21.0"

def refresh_token(tok):
    """Продлевает долгоживущий токен ещё на 60 дней (делается при каждом запуске)."""
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
    return r.json().get("access_token", tok) if r.ok else tok

def wait_public(url):
    for _ in range(40):  # Pages выкладывает файл 1-3 минуты
        r = requests.head(url, timeout=30)
        if r.ok: return
        time.sleep(15)
    raise RuntimeError(f"ссылка не открылась: {url}")

def publish(url: str, caption: str) -> str:
    uid = os.environ["IG_USER_ID"]
    tok = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    wait_public(url)
    c = requests.post(f"{API}/{uid}/media", data={"media_type": "REELS", "video_url": url,
                      "caption": caption, "share_to_feed": "true", "access_token": tok}).json()
    if "id" not in c: raise RuntimeError(c)
    cid = c["id"]
    for _ in range(60):  # ждём, пока Instagram скачает и обработает видео
        st = requests.get(f"{API}/{cid}", params={"fields": "status_code,status", "access_token": tok}).json()
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise RuntimeError(st)
        time.sleep(10)
    p = requests.post(f"{API}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}).json()
    if "id" not in p: raise RuntimeError(p)
    return p["id"]

if __name__ == "__main__":
    print("опубликовано, id:", publish(sys.argv[1], Path(sys.argv[2]).read_text(encoding="utf-8")))
