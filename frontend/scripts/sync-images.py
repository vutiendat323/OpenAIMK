"""Download public Trend Coffee photos and produce bounded local WebP assets.

Run: uv run --with pillow python frontend/scripts/sync-images.py --menu /path/to/public-menu.json
Only URLs published in the customer catalog are used; no writes to the merchant.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import quote
import subprocess
from PIL import Image, ImageOps

parser = argparse.ArgumentParser()
parser.add_argument('--menu', required=True)
args = parser.parse_args()
data = json.loads(Path(args.menu).read_text())
root = Path(__file__).resolve().parents[1] / 'public'
target = root / 'menu-images'
target.mkdir(parents=True, exist_ok=True)
rows = data['result']['items'][0]['menuItems']
products = {row['product']['slug']: row['product'] for row in rows if row['product'].get('image')}

def download(pair):
    product_id, product = pair
    image_id = product['image']
    if not isinstance(image_id, str) or not image_id or '/' in image_id or '\\' in image_id or '..' in image_id or len(image_id)>200:
        raise ValueError('Unexpected public image identifier')
    url = 'https://trendcoffee.s3.ap-southeast-1.amazonaws.com/' + quote(image_id, safe='')
    output = target / (product_id + '.webp')
    if not output.exists():
        raw = subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','20',url], timeout=22)
        with Image.open(BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im).convert('RGB')
            im.thumbnail((520,520))
            im.save(output, 'WEBP', quality=80, method=6)
    return product_id, {'src':'/menu-images/'+output.name, 'source_url':url, 'name':product['name']}

with ThreadPoolExecutor(max_workers=6) as pool:
    manifest = dict(pool.map(download, products.items()))
(root / 'menu-images.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print('Saved',len(manifest),'official product photos;',sum(p.stat().st_size for p in target.glob('*.webp')),'bytes')
