"""Restore the verified starting snapshot only when a checkout has no dataset yet."""
import base64,gzip,hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=ROOT/'data';data.mkdir(exist_ok=True)
snapshot=data/'latest_snapshot.json'
def seed_bytes(name):
    direct=ROOT/'seed'/name
    if direct.exists():return direct.read_bytes()
    manifest=json.loads((ROOT/'seed/manifest.json').read_text())[name]
    payload=base64.b64decode(''.join((ROOT/'seed'/part).read_text() for part in manifest['parts']),validate=True)
    if hashlib.sha256(payload).hexdigest()!=manifest['sha256']:raise ValueError('Seed checksum mismatch')
    return payload
if not snapshot.exists():
    snapshot.write_bytes(gzip.decompress(seed_bytes('initial_snapshot.json.gz')))
    with tarfile.open(fileobj=io.BytesIO(seed_bytes('initial_sources.tar.gz')),mode='r:gz') as archive:
        archive.extractall(data,filter='data')
if not (data/'us_macro.xlsx').exists():
    subprocess.run([sys.executable,str(ROOT/'updater/update_us_macro.py'),'--from-snapshot',str(snapshot)],check=True)
