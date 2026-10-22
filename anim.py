"""Анимированный стиль: 8-12 ИИ-иллюстраций на ролик, живая камера (наезды, панорамы, крен),
туман, пыль, мерцание света, «скример» с вспышкой и тряской, субтитры по словам, звуковой дизайн."""
import math, random, re, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1080, 1920, 30
STYLE = (", dark atmospheric horror illustration, detailed digital painting, cinematic animated film still, "
         "atmospheric haze, rich colors, dramatic contrast, sharp focus, highly detailed, vertical 9:16, no text")
FONT = "DejaVu Sans"
PALETTES = ["warm amber lamp light and deep shadows", "cold blue night light with warm window glow",
            "sickly green fluorescent light", "orange firelight and black shadows", "pale grey overcast daylight",
            "deep red accent light and darkness"]

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

# ---------- подготовка кадра ----------
def grade(img):
    """Единая цветокоррекция: холодные тени, тёплые света, контраст, чтобы картинки выглядели одной серией."""
    a = np.asarray(img.convert("RGB").resize((W, H), Image.LANCZOS), np.float32) / 255
    lum = a.mean(2, keepdims=True)
    shadow = np.array([0.80, 0.95, 1.10], np.float32)
    high = np.array([1.08, 1.0, 0.88], np.float32)
    a = a * (shadow * (1 - lum) + high * lum)
    a = np.clip((a - 0.5) * 1.12 + 0.52, 0, 1) ** 0.92
    return Image.fromarray((a * 255).astype(np.uint8))

def motion(rng, scare):
    """Случайное движение камеры для сцены: (зум0, зум1, сдвиг x0, x1, y0, y1, крен0, крен1)."""
    kind = rng.choice(["in", "out", "left", "right", "up", "down"])
    z0, z1 = (1.12, 1.32) if kind == "in" else (1.32, 1.12) if kind == "out" else (1.22, 1.26)
    dx = {"left": (60, -60), "right": (-60, 60)}.get(kind, (rng.uniform(-25, 25), rng.uniform(-25, 25)))
    dy = {"up": (90, -90), "down": (-90, 90)}.get(kind, (rng.uniform(-20, 20), rng.uniform(-20, 20)))
    r = rng.uniform(-1.2, 1.2)
    if scare:
        z0, z1 = 1.12, 1.45
    return z0, z1, dx, dy, (r, -r * 0.5)

def camera(img, z, cx, cy, rot):
    c, s = math.cos(math.radians(rot)) / z, math.sin(math.radians(rot)) / z
    x0, y0 = W / 2 + cx, H / 2 + cy
    data = (c, -s, x0 - c * W / 2 + s * H / 2, s, c, y0 - s * W / 2 - c * H / 2)
    return img.transform((W, H), Image.AFFINE, data, resample=Image.BICUBIC)

class Atmos:
    """Наложения поверх кадра: туман, пыль, зерно, виньетка, мерцание."""
    def __init__(self, seed):
        self.r = np.random.default_rng(seed)
        fog = Image.fromarray((self.r.random((24, 40)) * 255).astype(np.uint8)).resize((540, 480), Image.BICUBIC)
        self.fog = np.asarray(fog.filter(ImageFilter.GaussianBlur(18)), np.float32) / 255
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        self.vig = np.clip(1 - 0.35 * rr ** 2.6, 0.3, 1)[..., None]
        self.grain = [self.r.normal(0, 5, (H // 2, W // 2)).astype(np.float32).repeat(2, 0).repeat(2, 1)[..., None]
                      for _ in range(8)]
        self.dust = [[self.r.uniform(0, W), self.r.uniform(0, H), self.r.uniform(1.5, 4.5), self.r.uniform(-0.4, 0.4),
                      self.r.uniform(-1.2, -0.2), self.r.uniform(0.2, 0.7)] for _ in range(45)]

    def __call__(self, frame, k, t):
        d = ImageDraw.Draw(frame, "RGBA")
        for p in self.dust:                                   # пылинки в луче света
            p[0] = (p[0] + p[3] + 0.3 * math.sin(t + p[1])) % W
            p[1] = (p[1] + p[4]) % H
            a = int(255 * p[5] * (0.6 + 0.4 * math.sin(t * 3 + p[0])))
            d.ellipse([p[0] - p[2], p[1] - p[2], p[0] + p[2], p[1] + p[2]], fill=(255, 230, 200, a))
        a = np.asarray(frame, np.float32)
        off = int(t * 18) % 540                               # туман медленно ползёт
        fog = np.roll(self.fog, -off, 1)[:, :270]
        fog = np.asarray(Image.fromarray((fog * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32)
        fog = (fog / 255)[..., None] * np.linspace(0.03, 0.22, H, dtype=np.float32)[:, None, None]
        a = a + (210 - a) * fog * np.array([0.85, 0.95, 1.0], np.float32)
        flick = 1.0 if self.r.random() > 0.04 else self.r.uniform(0.75, 0.9)
        a = (a * self.vig * flick) + self.grain[k % 8]
        return np.clip(a, 0, 255).astype(np.uint8)

# ---------- субтитры: по 2-3 слова, текущее слово жёлтое и крупнее ----------
def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02}:{t % 60:05.2f}"

def subtitles(words, hook, path, total):
    head = f"""[Script Info]
PlayResX: {W}
PlayResY: {H}
WrapStyle: 1
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: S,{FONT},96,&H00FFFFFF,&H00000000,&H96000000,1,1,7,4,5,60,60,0
Style: Hook,{FONT},84,&H00FFFFFF,&H001A1AB4,&H001A1AB4,1,3,18,0,8,70,70,330
[Events]
Format: Layer, Start, End, Style, Text
"""
    ev = [f"Dialogue: 1,{ass_time(0)},{ass_time(2.6)},Hook,{{\\fad(0,250)\\t(0,120,\\fscx108\\fscy108)\\t(120,240,\\fscx100\\fscy100)}}{hook.upper()}"]
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) == 3 or re.search(r"[.,!?…:;—»]$", w[2]):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    for ci, ch in enumerate(chunks):
        end_chunk = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else min(ch[-1][1] + 0.4, total)
        for i, w in enumerate(ch):
            s, e = w[0], (ch[i + 1][0] if i + 1 < len(ch) else end_chunk)
            parts = []
            for j, x in enumerate(ch):
                t = x[2].upper()
                parts.append("{\\c&H00D7FF&\\fscx112\\fscy112}" + t + "{\\r}" if j == i else t)
            pop = "{\\pos(540,1290)\\t(0,90,\\fscx106\\fscy106)\\t(90,180,\\fscx100\\fscy100)}" if i == 0 else "{\\pos(540,1290)}"
            ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(max(e, s + 0.05))},S,{pop}{' '.join(parts)}")
    path.write_text(head + "\n".join(ev), encoding="utf-8")

# ---------- звук: гул, свист на склейках, удар на скримере ----------
def sfx(path, total, cuts, scares, sr=44100):
    n = int(total * sr)
    t = np.arange(n) / sr
    rng = np.random.default_rng(5)
    brown = np.cumsum(rng.normal(0, 1, n)).astype(np.float32)
    brown -= np.convolve(brown, np.ones(4000) / 4000, "same")
    brown /= np.abs(brown).max() + 1e-6
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t)
    out = (0.05 * (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 55.6 * t) + 0.4 * np.sin(2 * np.pi * 82.4 * t))
           + 0.08 * brown) * lfo * np.minimum(t / 1.5, 1)
    white = rng.normal(0, 1, n).astype(np.float32)
    for c in cuts:                                                         # свист на склейке
        s, L = int(max(c - 0.25, 0) * sr), int(0.4 * sr)
        seg = white[s:s + L]
        seg = np.convolve(seg, np.ones(12) / 12, "same")
        env = np.sin(np.linspace(0, np.pi, seg.size)) ** 2
        out[s:s + seg.size] += 0.10 * seg * env
    for c in scares:                                                       # удар + хвост
        s = int(c * sr)
        L = min(int(1.6 * sr), n - s)
        tt = np.arange(L) / sr
        boom = np.sin(2 * np.pi * (40 * tt + 30 * (1 - np.exp(-tt * 8)) / 8)) * np.exp(-tt * 2.5)
        hit = white[s:s + L] * np.exp(-tt * 18)
        out[s:s + L] += 0.55 * boom + 0.25 * hit
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

# ---------- сборка ----------
def build(script, d, mr):
    """mr — модуль make_reel (озвучка, картинки, длительность)."""
    mp3, words = mr.voiceover(script["narration"], d)
    total = mr.duration(mp3) + 0.8
    scenes = script["scenes"]
    n = len(scenes)
    # склейки — на начала слов, ближайшие к равномерной сетке
    starts = [w[0] for w in words] or [0]
    cuts = [0.0]
    for i in range(1, n):
        target = total * i / n
        c = min(starts, key=lambda s: abs(s - target))
        cuts.append(c if c > cuts[-1] + 1.2 else cuts[-1] + total / n)
    cuts.append(total)
    char = script.get("character", "")
    imgs = []
    for i, sc in enumerate(scenes):
        p = d / f"s{i}.jpg"
        prompt = sc["prompt"]
        if char and sc.get("character"):
            prompt = f"{char}, {prompt}"
        mr.image(prompt, p, random.randint(1, 10 ** 6), STYLE + ", " + PALETTES[i % len(PALETTES)])
        imgs.append(grade(Image.open(p)))
    scares = [cuts[i] for i, sc in enumerate(scenes) if sc.get("scare")][:2]
    subtitles(words, script.get("hook") or script["title"], d / "subs.ass", total)
    sfx(d / "sfx.wav", total, cuts[1:-1], scares, )
    out = d / "reel.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", str(mp3), "-i", str(d / "sfx.wav"), "-filter_complex",
         f"[0:v]ass={d / 'subs.ass'},format=yuv420p[v];[1:a]adelay=150|150,volume=1.7[vo];"
         f"[2:a]volume=0.9[fx];[vo][fx]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "9M", "-bufsize", "18M",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    rng = random.Random(len(script["narration"]))
    atm = Atmos(rng.randint(1, 999))
    moves = [motion(rng, sc.get("scare")) for sc in scenes]
    nf = int(total * FPS)
    for k in range(nf):
        t = k / FPS
        i = max(j for j in range(n) if cuts[j] <= t)
        lt, T = t - cuts[i], cuts[i + 1] - cuts[i]
        z0, z1, dx, dy, rot = moves[i]
        sc = scenes[i]
        if sc.get("scare"):
            e = 1 - (1 - min(lt / 0.35, 1)) ** 3                     # резкий наезд
            z = z0 + (z1 - z0) * e
            sh = 16 * math.exp(-lt * 4)
            cx = dx[0] + rng.uniform(-sh, sh); cy = dy[0] + rng.uniform(-sh, sh)
        else:
            e = ease(lt / T)
            z = z0 + (z1 - z0) * e
            cx, cy = dx[0] + (dx[1] - dx[0]) * e, dy[0] + (dy[1] - dy[0]) * e
        frame = camera(imgs[i], z, cx, cy, rot[0] + (rot[1] - rot[0]) * ease(lt / T))
        a = atm(frame, k, t)
        if sc.get("scare") and lt < 0.12:                              # вспышка
            a = np.clip(a.astype(np.int16) + 150, 0, 255).astype(np.uint8)
        elif sc.get("scare") and lt < 0.5:                             # расслоение цвета
            sft = int(10 * (1 - lt / 0.5))
            a = a.copy(); a[..., 0] = np.roll(a[..., 0], sft, 1); a[..., 2] = np.roll(a[..., 2], -sft, 1)
        if lt < 0.08 and i > 0 and not sc.get("scare"):                # мягкая склейка через затемнение
            a = (a * (0.45 + 0.55 * lt / 0.08)).astype(np.uint8)
        if total - t < 0.4:
            a = (a * max(total - t, 0) / 0.4).astype(np.uint8)
        ff.stdin.write(a.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError("ffmpeg не собрал ролик")
    tags = " ".join("#" + x.lstrip("#") for x in script["hashtags"])
    (d / "caption.txt").write_text(f"{script['caption']}\n\nСоздано с помощью ИИ.\n\n{tags}", encoding="utf-8")
    return out
