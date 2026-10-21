#!/usr/bin/env python3
"""Тёмный архив: сценарий -> озвучка -> видео 9:16 -> субтитры -> (опц.) публикация.
Запуск: python make_reel.py [--topic "..."]; публикация — post_instagram.py (см. workflow)."""
import argparse, asyncio, json, os, random, re, subprocess, sys, time, urllib.parse
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).parent
FALLBACKS = []  # что пришлось заменить заглушкой; с заглушками не публикуем
OUT = ROOT / "out"
W, H, FPS = 1080, 1920, 30
FONT = "DejaVu Sans"

def load_env():
    f = ROOT / "config.env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(path)]).strip())

# ---------- 1. Сценарий ----------
RULES = """Ты сценарист Reels-канала «Тёмный архив» (русский язык).
Жанр: {genre}. Длина текста озвучки: 55-85 слов (20-35 секунд).
Структура: первая фраза — крючок, цепляет за 2 секунды; дальше нарастание; финал — твист или вопрос, побуждающий подписаться/комментировать.
Тру-крайм: только старые широко известные дела, факты без выдумок, без жестоких подробностей, никаких несовершеннолетних жертв, фокус на загадке и расследовании.
Хоррор: оригинальная крипипаста или городская легенда, атмосфера, без натурализма.
Не повторяй темы: {used}.
Верни ТОЛЬКО JSON: {{"title": "...", "narration": "...", "scenes": ["4-6 англ. промптов для картинок: тёмная кинематографичная атмосфера, без лиц реальных людей, без крови"], "caption": "подпись 1-2 предложения", "hashtags": ["8-12 тегов без #"]}}"""

FALLBACK = {
    "title": "Голос в радионяне",
    "narration": "В две тысячи восьмом году молодая мать услышала в радионяне мужской голос. "
                 "Он тихо напевал колыбельную её спящему сыну. Она вбежала в детскую — никого. "
                 "Окна закрыты, дверь заперта изнутри. Полиция ничего не нашла. "
                 "А через неделю голос вернулся и сказал всего одну фразу: «Я всё ещё здесь». "
                 "Как вы думаете, кто это был? Подпишись, завтра расскажу, чем всё закончилось.",
    "scenes": ["dark nursery at night, baby monitor glowing green, cinematic, horror atmosphere",
               "empty dark hallway, door slightly open, moonlight, eerie",
               "old baby monitor close up, static noise, dark room",
               "window at night with fog outside, silhouette of trees, unsettling",
               "dark house exterior at night, single lit window, mist"],
    "caption": "Голос, который не должен был там быть.",
    "hashtags": ["хоррор", "страшныеистории", "крипипаста", "мистика", "тёмныйархив", "страшно", "reels", "ужасы"],
}

def _llm(prompt):
    """Бесплатные источники по очереди: GitHub Models (токен Actions), Gemini (бесплатный ключ), Pollinations."""
    msgs = [{"role": "user", "content": prompt}]
    tries = []
    if os.getenv("GITHUB_TOKEN"):
        gh = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/json"}
        tries.append(("GitHub Models", lambda: requests.post(
            "https://models.github.ai/inference/chat/completions", timeout=120, headers=gh,
            json={"model": "openai/gpt-4.1-mini", "messages": msgs})))
        tries.append(("GitHub Models (azure)", lambda: requests.post(
            "https://models.inference.ai.azure.com/chat/completions", timeout=120, headers=gh,
            json={"model": "gpt-4o-mini", "messages": msgs})))
    if os.getenv("GEMINI_API_KEY"):
        tries.append(("Gemini", lambda: requests.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", timeout=120,
            headers={"Authorization": f"Bearer {os.environ['GEMINI_API_KEY']}"},
            json={"model": "gemini-2.5-flash", "messages": msgs})))
    tries.append(("Pollinations", lambda: requests.post(
        "https://text.pollinations.ai/openai", timeout=180,
        json={"model": "openai", "messages": msgs, "max_tokens": 6000, "reasoning_effort": "low",
              "seed": random.randint(1, 10**6)})))
    for attempt in range(3):
        for name, call in tries:
            try:
                r = None
                r = call()
                text = r.json()["choices"][0]["message"].get("content") or ""
                if "{" in text:
                    return text
                raise ValueError("нет JSON в ответе")
            except Exception as e:
                body = f"HTTP {r.status_code} {r.text[:200]}" if r is not None else ""
                print(f"! {name}: {type(e).__name__} {body}")
        time.sleep(35)  # бесплатный лимит Pollinations: 1 ответ в 30 с
    raise RuntimeError("не удалось получить сценарий")

def write_script(topic=None, test=False):
    hist_f = ROOT / "history.json"
    used = json.loads(hist_f.read_text()) if hist_f.exists() else []
    if test:
        return FALLBACK
    genre = topic or ("хоррор" if random.random() < 0.6 else "тру-крайм")
    for attempt in range(3):
        text = _llm(RULES.format(genre=genre, used=", ".join(used[-60:]) or "нет"))
        try:
            data = json.loads(text[text.find("{"): text.rfind("}") + 1])
            assert data["narration"] and len(data["scenes"]) >= 3 and data["hashtags"]
            break
        except Exception as e:
            print(f"! кривой сценарий ({type(e).__name__}), заново")
    else:
        raise RuntimeError("сценарий не разобрался")
    used.append(data["title"])
    hist_f.write_text(json.dumps(used, ensure_ascii=False, indent=1))
    return data

# ---------- 2. Озвучка + тайминги слов ----------
async def _edge(text, mp3, voice):
    import edge_tts
    words = []
    com = edge_tts.Communicate(text, voice, rate="-5%", pitch="-8Hz", boundary="WordBoundary",
                               proxy=os.getenv("HTTPS_PROXY") or None)
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return words

def voiceover(text, d):
    mp3 = d / "voice.mp3"
    words = None
    for attempt in range(4):
        try:
            words = asyncio.run(_edge(text, mp3, os.getenv("VOICE", "ru-RU-DmitryNeural")))
            if words: break
        except Exception as e:
            print(f"! edge-tts: {type(e).__name__}, попытка {attempt + 1}")
        time.sleep(10 * (attempt + 1))
    if not words:  # офлайн-запасной вариант
        print("! edge-tts недоступен — espeak-ng")
        FALLBACKS.append("voice")
        wav = d / "voice.wav"
        run(["espeak-ng", "-v", "ru", "-s", "150", "-p", "30", "-w", str(wav), text])
        run(["ffmpeg", "-y", "-i", str(wav), str(mp3)])
        total, toks = duration(mp3), text.split()
        weight = [len(t) + 2 for t in toks]
        t, words = 0.0, []
        for tok, w in zip(toks, weight):
            dt = total * w / sum(weight)
            words.append((t, t + dt, tok)); t += dt
    return mp3, words

# ---------- 3. Субтитры (ASS, крупные, по 2-3 слова) ----------
def ass_time(t):
    return f"{int(t//3600)}:{int(t%3600//60):02}:{t%60:05.2f}"

def subtitles(words, path):
    head = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV
Style: S,{FONT},92,&H00FFFFFF,&H00000000,&H80000000,1,1,6,3,2,620
[Events]
Format: Layer, Start, End, Style, Text
"""
    lines, chunk = [], []
    for w in words:
        chunk.append(w)
        if len(chunk) == 3 or re.search(r"[.,!?…:;—]$", w[2]):
            txt = " ".join(c[2] for c in chunk).upper()
            lines.append(f"Dialogue: 0,{ass_time(chunk[0][0])},{ass_time(chunk[-1][1])},S,{{\\fad(60,0)}}{txt}")
            chunk = []
    if chunk:
        lines.append(f"Dialogue: 0,{ass_time(chunk[0][0])},{ass_time(chunk[-1][1])},S,{' '.join(c[2] for c in chunk).upper()}")
    path.write_text(head + "\n".join(lines), encoding="utf-8")

# ---------- 4. Картинки ----------
def procedural(path, seed):
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H), (5, 5, 8))
    dr = ImageDraw.Draw(img)
    c = rnd.choice([(40, 0, 0), (0, 25, 30), (20, 20, 35), (30, 25, 10)])
    for i in range(14):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(150, 600)
        dr.ellipse([x - r, y - r, x + r, y + r], fill=tuple(min(255, v + rnd.randint(0, 25)) for v in c))
    img.filter(ImageFilter.GaussianBlur(120)).save(path)

def image(prompt, path, seed):
    prov = os.getenv("IMAGE_PROVIDER", "pollinations")
    full = prompt + ", dark cinematic horror photo, film grain, low key lighting, vertical 9:16, no text"
    try:
        if prov == "pollinations":
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(full)}?width={W}&height={H}&nologo=true&seed={seed}"
            for attempt in range(4):
                r = requests.get(url, timeout=180)
                if r.ok: break
                print(f"! картинка: HTTP {r.status_code} {r.text[:120]}")
                time.sleep(30)
            r.raise_for_status(); path.write_bytes(r.content)
        elif prov == "openai":
            r = requests.post("https://api.openai.com/v1/images/generations", timeout=180,
                              headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                              json={"model": "gpt-image-1", "prompt": full, "size": "1024x1536"})
            r.raise_for_status()
            import base64; path.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
        else:
            raise RuntimeError("off")
        Image.open(path).convert("RGB").resize((W, H)).save(path)
    except Exception as e:
        print(f"! картинка через {prov} не вышла ({type(e).__name__}) — заглушка")
        FALLBACKS.append("image")
        procedural(path, seed)

# ---------- 5. Сборка ----------
def build(script, d):
    mp3, words = voiceover(script["narration"], d)
    total = duration(mp3) + 1.2
    subtitles(words, d / "subs.ass")
    n = len(script["scenes"]); seg = total / n
    clips = []
    for i, p in enumerate(script["scenes"]):
        img = d / f"s{i}.jpg"; image(p, img, random.randint(1, 10**6))
        clip = d / f"c{i}.mp4"; frames = int(seg * FPS) + 1
        zoom = "min(zoom+0.0009,1.25)" if i % 2 == 0 else "if(eq(on,0),1.25,max(zoom-0.0009,1))"
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-vf",
             f"scale={int(W*1.5)}:-2,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
             f"eq=brightness=-0.06:saturation=0.7,noise=alls=12:allf=t,vignette=PI/4",
             "-frames:v", str(frames), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", str(clip)])
        clips.append(clip)
    (d / "list.txt").write_text("".join(f"file '{c.name}'\n" for c in clips))
    out = d / "reel.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(d / "list.txt"), "-i", str(mp3),
         "-f", "lavfi", "-i", f"anoisesrc=c=brown:a=0.04:d={total}",
         "-f", "lavfi", "-i", f"sine=f=55:d={total}",
         "-filter_complex",
         f"[0:v]ass={d/'subs.ass'}[v];[2:a]lowpass=f=400[n];[3:a]volume=0.05[s];"
         f"[1:a]adelay=300|300,volume=1.6[vo];[vo][n][s]amix=inputs=3:duration=longest:normalize=0[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
         "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    tags = " ".join("#" + t.lstrip("#") for t in script["hashtags"])
    (d / "caption.txt").write_text(f"{script['caption']}\n\nСоздано с помощью ИИ.\n\n{tags}", encoding="utf-8")
    return out

def main():
    load_env()
    ap = argparse.ArgumentParser(); ap.add_argument("--topic"); ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    script = write_script(a.topic, a.test)
    d = OUT / time.strftime("%Y%m%d_%H%M%S"); d.mkdir(parents=True)
    (d / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1))
    out = build(script, d)
    print("готово:", out)
    if FALLBACKS:
        raise SystemExit(f"не публикую: заглушки вместо {sorted(set(FALLBACKS))}")
    (ROOT / "out" / "latest.txt").write_text(str(d))

if __name__ == "__main__":
    main()
