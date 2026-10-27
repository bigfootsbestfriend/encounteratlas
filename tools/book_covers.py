"""Download book covers (Open Library) into site/static/covers/books/<isbn10>.webp so pages don't depend on Open Library.
Run after adding books to data/media.json. Usage: uv run --with pillow python tools/book_covers.py"""
import io, json, os, time, urllib.request
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'static', 'covers', 'books')
os.makedirs(OUT, exist_ok=True)
for b in json.load(open(os.path.join(ROOT, 'data', 'media.json')))['books']:
    if not (b.get('cover') or b.get('cover_id')) or not b.get('isbn10'):
        continue
    dest = os.path.join(OUT, b['isbn10'] + '.webp')
    if os.path.exists(dest):
        continue
    u = (f'https://covers.openlibrary.org/b/id/{b["cover_id"]}-L.jpg' if b.get('cover_id')
         else f'https://covers.openlibrary.org/b/isbn/{b["isbn10"]}-L.jpg')
    for tries in range(4):
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'EncounterAtlas/1.0'}), timeout=60).read()
            break
        except Exception as e:  # Open Library throws the odd 502
            print('retry', b['isbn10'], e)
            time.sleep(3 * (tries + 1))
    else:
        continue
    im = Image.open(io.BytesIO(data)).convert('RGB')
    im.thumbnail((300, 450))
    im.save(dest, quality=82)
    print(b['isbn10'], im.size)
    time.sleep(0.5)
