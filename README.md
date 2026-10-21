# Тёмный архив — конвейер Reels (бесплатно)
Сценарий: Pollinations (без ключа) или Gemini (бесплатный ключ) → голос edge-tts → картинки Pollinations → ffmpeg → Instagram API.
Автозапуск: GitHub Actions 3 раза в день (.github/workflows/reels.yml). Секреты: IG_USER_ID, IG_ACCESS_TOKEN, (опц.) GEMINI_API_KEY.
Локально: pip install -r requirements.txt; python make_reel.py --post   (тест без сети: --test)
