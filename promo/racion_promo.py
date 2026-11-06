#!/usr/bin/env python3
"""Промо-ролик приложения «Рацион» 9:16. Кадры рисуются PIL, звук: edge-tts озвучка + синтезированная музыка.
Запуск: python racion_promo.py <папка_с_озвучкой> <voice_prefix> <out.mp4>
Озвучка: файлы <prefix>_0.mp3 ... <prefix>_5.mp3 (по сцене на файл)."""
import math, os, subprocess, sys, wave, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FD = "/usr/share/fonts/opentype/inter/"
def F(sz, w="Bold"):
    return ImageFont.truetype(f"{FD}Inter-{w}.otf", sz)
EMOJI_FONT = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)

BG = (246, 243, 236); DARK = (29, 43, 36); GREEN = (45, 190, 108); GREEN2 = (22, 140, 80)
ORANGE = (255, 138, 61); RED = (255, 90, 95); WHITE = (255, 255, 255); GREY = (130, 140, 135)
BLUE = (76, 141, 255); YELLOW = (255, 200, 60)

def clamp(x, a=0., b=1.): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def back(x):
    x = clamp(x); c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2
def lerp(a, b, t): return a + (b - a) * t
def seg(t, a, b): return clamp((t - a) / (b - a))

_ecache = {}
def emoji(ch, size):
    key = (ch, size)
    if key not in _ecache:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((80, 80), ch, font=EMOJI_FONT, embedded_color=True, anchor="mm")
        im = im.crop(im.getbbox() or (0, 0, 160, 160))
        s = size / max(im.size)
        _ecache[key] = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return _ecache[key]

def paste_c(dst, im, cx, cy, scale=1., rot=0., alpha=1.):
    if scale <= 0.01 or alpha <= 0.01: return
    if scale != 1: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if rot: im = im.rotate(rot, Image.BILINEAR, expand=True)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    dst.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

def text_img(s, font, fill, stroke=0, sfill=None):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), s, font=font, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), s, font=font, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return im

_tcache = {}
def txt(dst, s, font_sz, fill, cx, cy, w="Bold", scale=1., alpha=1., rot=0., stroke=0, sfill=None):
    key = (s, font_sz, fill, w, stroke, sfill)
    if key not in _tcache: _tcache[key] = text_img(s, F(font_sz, w), fill, stroke, sfill)
    paste_c(dst, _tcache[key], cx, cy, scale, rot, alpha)

def rrect(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)

def shadow_card(img, box, r, fill, sh=18, alpha=60):
    x0, y0, x1, y1 = [int(v) for v in box]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle((x0, y0 + sh // 2, x1, y1 + sh), r, fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(sh))
    img.alpha_composite(layer)
    ImageDraw.Draw(img).rounded_rectangle((x0, y0, x1, y1), r, fill=fill)

def vgrad(c1, c2, w=W, h=H):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(c1)[None, None] * (1 - a) + np.array(c2)[None, None] * a).repeat(w, 1)
    im = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA"); return im

GRAD_DARK = vgrad((24, 38, 31), (40, 62, 50))
GRAD_LIGHT = vgrad((250, 248, 242), (236, 244, 236))
GRAD_GREEN = vgrad((52, 205, 120), (18, 128, 72))

# ---------- телефон ----------
PW, PH = 640, 1290
SW, SH = PW - 36, PH - 36
_pmask = Image.new("L", (SW, SH), 0); ImageDraw.Draw(_pmask).rounded_rectangle((0, 0, SW - 1, SH - 1), 62, fill=255)
def phone(img, screen, cx, cy, scale=1., rot=0.):
    ph = Image.new("RGBA", (PW + 80, PH + 80), (0, 0, 0, 0))
    sh = Image.new("RGBA", ph.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 60, 40 + PW, 60 + PH), 80, fill=(0, 0, 0, 90))
    ph.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(ph)
    d.rounded_rectangle((40, 40, 40 + PW, 40 + PH), 80, fill=(20, 22, 24))
    sc = screen.copy(); sc.putalpha(_pmask)
    ph.alpha_composite(sc, (58, 58))
    d.rounded_rectangle((40 + PW // 2 - 70, 76, 40 + PW // 2 + 70, 112), 18, fill=(10, 10, 10))
    paste_c(img, ph, cx, cy, scale, rot)

def status_bar(d, dark=False):
    c = WHITE if dark else DARK
    d.text((60, 52), "9:41", font=F(30, "SemiBold"), fill=c, anchor="lm")
    for i in range(3):
        d.rounded_rectangle((SW - 150 + i * 14, 60 - i * 6, SW - 140 + i * 14, 64), 2, fill=c)
    d.rounded_rectangle((SW - 92, 42, SW - 44, 64), 6, outline=c, width=3)
    d.rounded_rectangle((SW - 88, 46, SW - 56, 60), 3, fill=c)

def logo(img, cx, cy, s=1., alpha=1.):
    L = Image.new("RGBA", (420, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.ellipse((10, 10, 410, 410), fill=WHITE)
    d.ellipse((34, 34, 386, 386), fill=GREEN)
    paste_c(L, emoji("🥗", 220), 210, 220)
    paste_c(L, emoji("🌿", 110), 318, 92, rot=-20)
    paste_c(img, L, cx, cy, s, alpha=alpha)

# ---------- сцены ----------
FOODS = ["🍕", "🍔", "🥗", "🍣", "🥑", "🍩", "🍝", "🌮", "🍗", "🥐", "🍜", "🍫"]
random.seed(7)
FLY = [(random.uniform(80, W - 80), random.uniform(-200, H), random.uniform(90, 170), random.uniform(-40, 40),
        random.uniform(120, 260), random.choice(FOODS), random.uniform(0, 6.28)) for _ in range(16)]

def s_hook(t, D):
    img = GRAD_DARK.copy()
    for x, y0, sz, rs, sp, ch, ph in FLY:
        y = (y0 + t * sp) % (H + 300) - 150
        paste_c(img, emoji(ch, int(sz)), x + 30 * math.sin(t * 2 + ph), y, rot=rs * t + ph * 30, alpha=0.4)
    veil = Image.new("RGBA", (W, H), (20, 32, 26, 120)); img.alpha_composite(veil)
    k1 = back(seg(t, 0.0, 0.35)); k2 = back(seg(t, 0.45, 0.8))
    txt(img, "Опять", 120, WHITE, W / 2, 700, "ExtraBold", k1)
    txt(img, "не знаешь,", 120, WHITE, W / 2, 840, "ExtraBold", back(seg(t, 0.15, 0.5)))
    txt(img, "что съесть?", 132, ORANGE, W / 2, 1000, "Black", k2, rot=3 * math.sin(t * 6) * (1 - seg(t, 0.8, 1.5)))
    bob = 30 * math.sin(t * 5)
    paste_c(img, emoji("🤔", 260), W / 2, 1330 + bob, back(seg(t, 0.6, 1.0)), rot=8 * math.sin(t * 3))
    return img

NOTE = [("Яблоко 150 г", "78"), ("Хлеб 2 куска", "184?"), ("Сыр 40 г …", "1??"), ("Масло… сколько?", "??"), ("Итого:", "≈ ???")]
def s_manual(t, D):
    img = GRAD_LIGHT.copy(); d = ImageDraw.Draw(img)
    txt(img, "Считать калории", 92, DARK, W / 2, 300, "ExtraBold", back(seg(t, 0, 0.35)))
    txt(img, "вручную?", 92, DARK, W / 2, 410, "ExtraBold", back(seg(t, 0.1, 0.45)))
    y0 = 560; shadow_card(img, (140, y0, 940, y0 + 760), 40, (255, 253, 240)); d = ImageDraw.Draw(img)
    for i in range(9): d.line((180, y0 + 120 + i * 72, 900, y0 + 120 + i * 72), fill=(200, 215, 235), width=3)
    d.line((240, y0 + 30, 240, y0 + 730), fill=(255, 170, 170), width=4)
    for i, (a, b) in enumerate(NOTE):
        k = seg(t, 0.25 + i * 0.28, 0.5 + i * 0.28)
        if k <= 0: continue
        n = int(len(a) * k)
        d.text((270, y0 + 105 + i * 120), a[:n], font=F(50, "Medium"), fill=(40, 60, 120), anchor="ls")
        if k >= 1: d.text((880, y0 + 105 + i * 120), b, font=F(50, "SemiBold"), fill=(40, 60, 120), anchor="rs")
    paste_c(img, emoji("✏️", 120), 820 + 20 * math.sin(t * 14), y0 + 650 + 10 * math.cos(t * 11), rot=-10)
    paste_c(img, emoji("🧮", 170), 190, y0 + 760, back(seg(t, 0.5, 0.9)), rot=-12)
    kx = seg(t, D - 1.3, D - 0.9)
    if kx > 0:
        d = ImageDraw.Draw(img)
        d.line((170, y0 + 60, lerp(170, 910, kx), lerp(y0 + 60, y0 + 700, kx)), fill=RED, width=22)
        if kx >= 1:
            k2 = seg(t, D - 0.9, D - 0.6)
            d.line((910, y0 + 60, lerp(910, 170, k2), lerp(y0 + 60, y0 + 700, k2)), fill=RED, width=22)
    k3 = back(seg(t, D - 1.0, D - 0.6))
    txt(img, "Долго и скучно", 84, RED, W / 2, 1520, "Black", k3)
    paste_c(img, emoji("😩", 200), W / 2, 1700, k3)
    return img

GOALS = ["Похудеть", "Набрать форму", "ПП"]
MEALS = [("🥣", "Завтрак", "Овсянка с ягодами", 420), ("🍲", "Обед", "Суп + курица с рисом", 610),
         ("🐟", "Ужин", "Лосось и овощи", 480), ("🍎", "Перекус", "Яблоко, орехи", 150)]
def screen_menu(t, D):
    s = Image.new("RGBA", (SW, SH), (247, 249, 247, 255)); d = ImageDraw.Draw(s); status_bar(d)
    d.text((44, 160), "Привет, Саша 👋".replace(" 👋", ""), font=F(40, "SemiBold"), fill=GREY)
    d.text((44, 210), "Твоё меню", font=F(64, "ExtraBold"), fill=DARK)
    gi = min(2, int(seg(t, 1.6, D - 0.6) * 3)) if t > 1.6 else 0
    x = 44
    for i, g in enumerate(GOALS):
        tw = d.textlength(g, font=F(34, "SemiBold")) + 52
        on = i == gi
        rrect(d, (x, 320, x + tw, 390), 35, GREEN if on else (230, 236, 232))
        d.text((x + tw / 2, 355), g, font=F(34, "SemiBold"), fill=WHITE if on else DARK, anchor="mm"); x += tw + 16
    tot = 0
    for i, (e, n, desc, kc) in enumerate(MEALS):
        k = ease(seg(t, 0.9 + i * 0.35, 1.4 + i * 0.35))
        if k <= 0: continue
        y = 430 + i * 170; ox = (1 - k) * 600
        shadow_card(s, (30 + ox, y, SW - 30 + ox, y + 150), 34, WHITE, sh=10, alpha=35); d = ImageDraw.Draw(s)
        rrect(d, (52 + ox, y + 22, 158 + ox, y + 128), 28, (236, 248, 240))
        paste_c(s, emoji(e, 74), 105 + ox, y + 75)
        d.text((185 + ox, y + 50), n, font=F(38, "Bold"), fill=DARK, anchor="lm")
        d.text((185 + ox, y + 100), desc, font=F(28, "Regular"), fill=GREY, anchor="lm")
        d.text((SW - 60 + ox, y + 75), f"{kc}", font=F(40, "ExtraBold"), fill=GREEN2, anchor="rm")
        tot += kc * k
    by = 1130; rrect(d, (30, by, SW - 30, by + 110), 34, DARK)
    d.text((70, by + 55), "Итого за день", font=F(34, "SemiBold"), fill=WHITE, anchor="lm")
    d.text((SW - 70, by + 55), f"{int(tot)} ккал", font=F(42, "ExtraBold"), fill=(120, 240, 170), anchor="rm")
    return s

def s_menu(t, D):
    img = GRAD_GREEN.copy()
    for i in range(6):
        paste_c(img, emoji(["🥦", "🍓", "🥕", "🍋", "🥑", "🍇"][i], 120), [120, 960, 90, 990, 150, 930][i],
                [520, 640, 1400, 1500, 1800, 1830][i] + 18 * math.sin(t * 2 + i), rot=10 * math.sin(t + i), alpha=0.9)
    k = seg(t, 0, 0.9)
    if t < 1.4:
        logo(img, W / 2, 820, back(seg(t, 0, 0.5)) * lerp(1, 0.6, seg(t, 0.9, 1.4)))
        txt(img, "Рацион", 150, WHITE, W / 2, 1140, "Black", back(seg(t, 0.2, 0.6)), alpha=1 - seg(t, 0.9, 1.3))
    kp = ease(seg(t, 1.0, 1.6))
    if kp > 0:
        txt(img, "Меню под твою цель", 72, WHITE, W / 2, 190, "ExtraBold", back(seg(t, 1.1, 1.5)))
        phone(img, screen_menu(t - 0.6, D - 0.6), W / 2, lerp(H + 700, 1060, kp), 0.98, rot=lerp(8, 0, kp))
    return img

def ring(d, cx, cy, r, w, frac, col, bg=(235, 238, 236)):
    d.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=bg, width=w)
    if frac > 0: d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * frac, fill=col, width=w)

def screen_scan(t, D):
    s = Image.new("RGBA", (SW, SH), (18, 18, 20, 255)); d = ImageDraw.Draw(s)
    # «камера»: стол + тарелка
    d.rectangle((0, 0, SW, SH), fill=(120, 86, 60))
    for i in range(0, SH, 90): d.line((0, i, SW, i + 40), fill=(108, 76, 52), width=8)
    d.ellipse((SW / 2 - 250, 380, SW / 2 + 250, 880), fill=(250, 250, 248)); d.ellipse((SW / 2 - 200, 430, SW / 2 + 200, 830), fill=(238, 238, 235))
    paste_c(s, emoji("🍝", 330), SW / 2, 635, 1 + 0.03 * math.sin(t * 3))
    status_bar(d, dark=True)
    found = seg(t, 1.5, 2.0)
    c = tuple(int(lerp(a, b, found)) for a, b in zip(WHITE, GREEN))
    m = 40 * (1 - ease(seg(t, 0.2, 0.8)))
    x0, y0, x1, y1 = SW / 2 - 280 - m, 340 - m, SW / 2 + 280 + m, 930 + m
    for (px, py, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line((px, py, px + 80 * dx, py), fill=c, width=10); d.line((px, py, px, py + 80 * dy), fill=c, width=10)
    if t < 1.6:
        sy = lerp(y0 + 20, y1 - 20, (math.sin(t * 4) + 1) / 2)
        gl = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); ImageDraw.Draw(gl).rectangle((x0 + 20, sy - 6, x1 - 20, sy + 6), fill=(80, 255, 160, 220))
        s.alpha_composite(gl.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(s)
    rrect(d, (SW / 2 - 60, 1110, SW / 2 + 60, 1230), 60, None, outline=WHITE, width=8)
    d.ellipse((SW / 2 - 44, 1126, SW / 2 + 44, 1214), fill=WHITE)
    kr = ease(seg(t, 1.7, 2.3))
    if kr > 0:
        py = lerp(SH, 600, kr)
        rrect(d, (0, py, SW, SH + 80), 50, WHITE)
        d.rounded_rectangle((SW / 2 - 50, py + 18, SW / 2 + 50, py + 28), 5, fill=(220, 220, 220))
        d.text((44, py + 80), "Паста болоньезе", font=F(46, "ExtraBold"), fill=DARK, anchor="lm")
        kc = int(520 * ease(seg(t, 2.0, 3.0)))
        d.text((44, py + 145), f"{kc} ккал · 1 порция", font=F(34, "SemiBold"), fill=GREEN2, anchor="lm")
        for i, (nm, val, col) in enumerate([("Белки", 24, BLUE), ("Жиры", 18, YELLOW), ("Углеводы", 64, ORANGE)]):
            k = ease(seg(t, 2.2 + i * 0.35, 3.2 + i * 0.35)); cx = 105 + i * 197
            ring(d, cx, py + 300, 72, 18, k * val / 80, col)
            d.text((cx, py + 300), f"{int(val * k)} г", font=F(34, "ExtraBold"), fill=DARK, anchor="mm")
            d.text((cx, py + 410), nm, font=F(28, "SemiBold"), fill=GREY, anchor="mm")
    return s

def s_scan(t, D):
    img = GRAD_LIGHT.copy()
    txt(img, "Фото блюда →", 76, DARK, W / 2, 175, "ExtraBold", back(seg(t, 0, 0.35)))
    txt(img, "калории и КБЖУ", 76, GREEN2, W / 2, 270, "Black", back(seg(t, 0.15, 0.5)))
    kp = ease(seg(t, 0, 0.5))
    phone(img, screen_scan(t, D), W / 2, lerp(H + 600, 1120, kp), 0.95)
    if t > 1.5:
        paste_c(img, emoji("✨", 110), 140, 760 + 10 * math.sin(t * 5), back(seg(t, 1.5, 1.9)))
        paste_c(img, emoji("📸", 120), 950, 560, back(seg(t, 0.4, 0.8)), rot=12)
    else:
        paste_c(img, emoji("📸", 120), 950, 560, back(seg(t, 0.4, 0.8)), rot=12)
    return img

RECIPES = [("🥑", "Тост с авокадо", "10 мин · 320 ккал"), ("🍛", "Курица карри", "25 мин · 540 ккал"),
           ("🥞", "Сырники", "15 мин · 380 ккал"), ("🥗", "Боул с киноа", "20 мин · 450 ккал")]
SHOP = ["Авокадо — 2 шт", "Куриное филе — 500 г", "Творог 5% — 400 г", "Яйца — 10 шт"]
def s_recipes(t, D):
    img = GRAD_DARK.copy(); d = ImageDraw.Draw(img)
    txt(img, "Рецепты и список", 80, WHITE, W / 2, 190, "ExtraBold", back(seg(t, 0, 0.3)))
    txt(img, "покупок — за секунды", 80, (120, 240, 170), W / 2, 290, "ExtraBold", back(seg(t, 0.1, 0.4)))
    off = -t * 230 + 300
    for i, (e, n, m) in enumerate(RECIPES * 2):
        x = off + i * 470
        if x < -500 or x > W + 50: continue
        shadow_card(img, (x, 400, x + 430, 900), 40, WHITE, sh=14, alpha=80); d = ImageDraw.Draw(img)
        rrect(d, (x + 20, 420, x + 410, 700), 30, [(255, 240, 220), (230, 246, 236), (255, 232, 232), (232, 240, 255)][i % 4])
        paste_c(img, emoji(e, 190), x + 215, 560)
        d.text((x + 30, 760), n, font=F(40, "ExtraBold"), fill=DARK, anchor="lm")
        d.text((x + 30, 830), m, font=F(30, "SemiBold"), fill=GREY, anchor="lm")
    kc = ease(seg(t, 0.4, 0.9)); y = lerp(H, 1000, kc)
    shadow_card(img, (90, y, W - 90, y + 760), 44, WHITE, sh=14, alpha=80); d = ImageDraw.Draw(img)
    d.text((140, y + 80), "🛒", font=EMOJI_FONT, embedded_color=True, anchor="lm") if False else None
    paste_c(img, emoji("🛒", 72), 175, y + 85)
    d.text((240, y + 85), "Список покупок", font=F(48, "ExtraBold"), fill=DARK, anchor="lm")
    for i, it in enumerate(SHOP):
        yy = y + 210 + i * 130; k = seg(t, 1.0 + i * 0.45, 1.25 + i * 0.45)
        rrect(d, (140, yy - 36, 212, yy + 36), 18, GREEN if k > 0 else WHITE, outline=GREEN, width=5)
        if k > 0:
            d.line((156, yy, lerp(156, 172, min(1, k * 2)), lerp(yy, yy + 18, min(1, k * 2))), fill=WHITE, width=9)
            if k > 0.5: d.line((172, yy + 18, lerp(172, 198, (k - .5) * 2), lerp(yy + 18, yy - 20, (k - .5) * 2)), fill=WHITE, width=9)
        d.text((245, yy), it, font=F(42, "SemiBold"), fill=GREY if k >= 1 else DARK, anchor="lm")
        if k >= 1:
            tw = d.textlength(it, font=F(42, "SemiBold")); d.line((245, yy + 2, 245 + tw, yy + 2), fill=GREY, width=4)
    return img

def s_cta(t, D):
    img = GRAD_GREEN.copy()
    random.seed(3)
    for i in range(22):
        x = random.uniform(0, W); sp = random.uniform(200, 420); ph = random.uniform(0, 6)
        y = -150 + ((t + ph) * sp) % (H + 300)
        paste_c(img, emoji(random.choice(FOODS + ["🥦", "🍓", "🥕"]), int(random.uniform(70, 120))), x, y,
                rot=(t * 90 + ph * 50) % 360, alpha=0.5)
    logo(img, W / 2, 620, back(seg(t, 0, 0.45)) * (1 + 0.03 * math.sin(t * 4)))
    txt(img, "Рацион", 170, WHITE, W / 2, 960, "Black", back(seg(t, 0.15, 0.55)))
    txt(img, "Ешь вкусно —", 78, WHITE, W / 2, 1140, "Bold", back(seg(t, 0.8, 1.2)))
    txt(img, "живи легко", 78, (255, 236, 160), W / 2, 1240, "ExtraBold", back(seg(t, 1.1, 1.5)))
    kb = back(seg(t, 1.9, 2.3)) * (1 + 0.05 * math.sin(t * 7) * seg(t, 2.3, 2.6))
    if kb > 0:
        b = Image.new("RGBA", (760, 180), (0, 0, 0, 0)); bd = ImageDraw.Draw(b)
        bd.rounded_rectangle((0, 0, 759, 179), 90, fill=WHITE)
        bd.text((380, 92), "Скачать бесплатно", font=F(58, "ExtraBold"), fill=GREEN2, anchor="mm")
        paste_c(img, b, W / 2, 1490, kb)
        txt(img, "iOS · Android", 44, WHITE, W / 2, 1640, "SemiBold", alpha=seg(t, 2.4, 2.8))
    if 2.6 < t:
        paste_c(img, emoji("👆", 150), W / 2 + 340, 1620 + 25 * math.sin(t * 6), back(seg(t, 2.6, 3.0)), rot=-15)
    return img

SCENES = [s_hook, s_manual, s_menu, s_scan, s_recipes, s_cta]

# ---------- звук ----------
SR = 44100
def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))

def wav_write(path, x):
    x = np.clip(x, -1, 1); a = (x * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2 if a.ndim == 2 else 1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())

def music(total, bounds):
    n = int(total * SR); out = np.zeros((n, 2)); bpm = 112; beat = 60 / bpm
    tt = np.arange(n) / SR
    notes = {"C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.0, "A": 440.0, "B": 493.88}
    prog = [("C", "E", "G"), ("A", "C", "E"), ("F", "A", "C"), ("G", "B", "D")]
    bar = beat * 4
    def tone(f, L, kind="pluck"):
        x = np.arange(int(L * SR)) / SR
        if kind == "pluck":
            s = (np.sin(2 * np.pi * f * x) + 0.4 * np.sin(4 * np.pi * f * x) + 0.15 * np.sin(6 * np.pi * f * x)) * np.exp(-x * 7)
        else:
            s = (np.sin(2 * np.pi * f * x) + 0.3 * np.sin(2 * np.pi * f * 2.005 * x)) * np.minimum(1, x * 6) * np.minimum(1, (L - x) * 6)
        return s
    def add(sig, t0, gain, pan=0.):
        i = int(t0 * SR); j = min(n, i + len(sig))
        if i >= n: return
        out[i:j, 0] += sig[:j - i] * gain * (1 - pan); out[i:j, 1] += sig[:j - i] * gain * (1 + pan)
    start = 0.0
    b = 0
    while start < total:
        ch = prog[b % 4]
        for nt in ch: add(tone(notes[nt] / 2, bar, "pad"), start, 0.05)
        add(tone(notes[ch[0]] / 4, bar, "pad"), start, 0.08)
        arp = [ch[0], ch[1], ch[2], ch[1]] * 2
        for k, nt in enumerate(arp):
            add(tone(notes[nt] * 2, beat, "pluck"), start + k * beat / 2, 0.06, pan=0.4 if k % 2 else -0.4)
        for k in range(4):
            kt = np.arange(int(0.25 * SR)) / SR
            kick = np.sin(2 * np.pi * (50 + 120 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)
            add(kick, start + k * beat, 0.35)
            hh = np.random.randn(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 80)
            hh = np.diff(hh, prepend=0)
            add(hh, start + k * beat + beat / 2, 0.06)
            if k in (1, 3):
                cl = np.random.randn(int(0.12 * SR)) * np.exp(-np.arange(int(0.12 * SR)) / SR * 30)
                add(cl, start + k * beat, 0.07)
        start += bar; b += 1
    # whoosh на стыках сцен
    for tb in bounds:
        L = 0.45; x = np.arange(int(L * SR)) / SR
        nz = np.random.randn(len(x)); nz = np.convolve(nz, np.ones(8) / 8, "same")
        env = np.sin(np.pi * x / L) ** 2
        add(nz * env, tb - L * 0.6, 0.12)
    # fade out
    fo = int(1.2 * SR); out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return out

def main():
    vdir, pref, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    tmp = os.path.join(os.path.dirname(os.path.abspath(outp)), "_promo_tmp"); os.makedirs(tmp, exist_ok=True)
    LEAD, GAP, TAIL = 0.35, 0.35, 1.6
    vfiles = [os.path.join(vdir, f"{pref}_{i}.mp3") for i in range(6)]
    vd = [dur(p) for p in vfiles]
    starts, sdur, t = [], [], 0.0
    for i, d in enumerate(vd):
        lead = LEAD if i == 0 else GAP
        starts.append(t + lead); L = lead + d + (TAIL if i == 5 else 0.0)
        sdur.append(L); t += L
    total = t
    bounds = np.cumsum([0] + sdur)
    print("сцены:", [round(x, 2) for x in sdur], "итого", round(total, 2))
    # голос
    voice = np.zeros((int(total * SR) + SR, 2))
    for i, p in enumerate(vfiles):
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
        a = np.frombuffer(raw, np.float32); j = int(starts[i] * SR)
        voice[j:j + len(a)] += a[:, None]
    voice = voice[:int(total * SR)]
    m = music(total, bounds[1:-1])
    env = np.abs(voice[:, 0]); k = int(0.15 * SR)
    env = np.convolve(env, np.ones(k) / k, "same"); duck = 1 - 0.55 * np.clip(env * 12, 0, 1)
    mix = voice * 1.35 + m * duck[:, None]
    mix /= max(1.0, np.abs(mix).max() / 0.95)
    wav_write(os.path.join(tmp, "mix.wav"), mix)
    # видео
    nfr = int(total * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-i", os.path.join(tmp, "mix.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outp],
                          stdin=subprocess.PIPE)
    prev_last = None; cur = -1; XF = 0.22
    for f in range(nfr):
        tg = f / FPS
        si = int(np.searchsorted(bounds, tg, side="right") - 1); si = min(si, 5)
        lt = tg - bounds[si]
        fr = SCENES[si](lt, sdur[si]).convert("RGB")
        if si != cur:
            if cur >= 0: prev_last = SCENES[cur](sdur[cur], sdur[cur]).convert("RGB")
            cur = si
        if prev_last is not None and lt < XF:
            k = ease(lt / XF)
            z = 1 + 0.08 * (1 - k)
            zz = fr.resize((int(W * z), int(H * z)), Image.BILINEAR).crop((int((W * z - W) / 2), int((H * z - H) / 2), int((W * z - W) / 2) + W, int((H * z - H) / 2) + H))
            fr = Image.blend(prev_last, zz, k)
        ff.stdin.write(fr.tobytes())
        if f % 150 == 0: print(f"кадр {f}/{nfr}", flush=True)
    ff.stdin.close(); ff.wait()
    print("готово:", outp)

if __name__ == "__main__":
    main()
