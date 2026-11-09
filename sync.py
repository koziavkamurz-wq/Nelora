"""Publish only public, checksum-verified Nulora APT files; no local data."""
import hashlib
import pathlib
import re
import urllib.request
import urllib.parse
import json

base = 'https://nuloraos.github.io/TheIpOS/'
out = pathlib.Path('public')
out.mkdir(exist_ok=True)
def read(name, maximum=2*1024*1024):
    with urllib.request.urlopen(base + name, timeout=90) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Response too large')
    return data

index = read('Packages')
packages = []
for block in index.decode('utf8').split('\n\n'):
    fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
    if not fields.get('Package'):
        continue
    relative = fields['Filename'].removeprefix('./')
    if not re.fullmatch(r'[A-Za-z0-9_./+\-]+', relative) or '..' in relative.split('/') or relative.startswith('/'):
        raise ValueError('Unsafe package path')
    data = read(relative, 64*1024*1024)
    if hashlib.sha256(data).hexdigest() != fields['SHA256'] or len(data) != int(fields['Size']):
        raise ValueError('Package integrity mismatch')
    dest = out / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    packages.append(fields)
if not packages:
    raise ValueError('Empty source')
for name in ['Release', 'Packages', 'Packages.gz', 'Packages.bz2']:
    (out / name).write_bytes(index if name == 'Packages' else read(name))
# Check all compressed indexes against Release, so an interrupted upstream deploy cannot mix generations.
release = (out / 'Release').read_text()
for name in ['Packages', 'Packages.gz', 'Packages.bz2']:
    data = (out / name).read_bytes()
    expected = f' {hashlib.sha256(data).hexdigest()} {len(data)} {name}'
    if expected not in release:
        raise ValueError('Index integrity mismatch')
(out / '.nojekyll').touch()
(out / 'CydiaIcon.png').write_bytes(read('icons/nulora-motion.png'))
items = ''.join(f'<li>{p["Name"]} {p["Version"]}</li>' for p in packages)
cards = []
for p in packages:
    kind = 'camera' if p['Package'].endswith('.camera') else 'motion' if p['Package'].endswith('.motion') else 'glass' if p['Package'].endswith('.glass') else 'dock'
    icon = f'icons/nulora-{kind}.png'
    (out / 'icons').mkdir(exist_ok=True)
    (out / icon).write_bytes(read(icon))
    descriptions = {'camera': 'Удержание горизонта, запись обработанного видео и экранный свет: белый или тёплый жёлтый.', 'motion': 'Направленное размытие при прокрутке и анимациях UIKit. Сила и области применения — в настройках.', 'dock': 'Полупрозрачная закруглённая панель с пятью местами для приложений. Свои настройки радиуса и прозрачности.', 'glass': 'Стеклянное оформление панелей, уведомлений и фона настоящей строки времени и батареи.'}
    cards.append(dict(name=p['Name'], version=p['Version'], file=p['Filename'], sha=p['SHA256'], icon=icon, category=kind if kind in ['camera','motion'] else 'theme', description=descriptions[kind], mirror=f'https://github.com/NuloraOS/TheIpOS/releases/download/v{p["Version"]}/'+pathlib.PurePosixPath(p['Filename']).name))
serialized = json.dumps(cards, ensure_ascii=False).replace('<', '\\u003c')
(out / 'index.html').write_text(pathlib.Path('index.template.html').read_text().replace('__PACKAGES__', serialized), encoding='utf8')
print(f'Published {len(packages)} verified packages')
