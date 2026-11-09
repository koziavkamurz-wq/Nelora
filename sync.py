"""Publish only public, checksum-verified Nulora APT files; no local data."""
import hashlib
import pathlib
import re
import urllib.request
import urllib.parse
import bz2
import gzip
import shutil

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
blocks = []
for block in index.decode('utf8').split('\n\n'):
    fields = dict(line.split(': ', 1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
    if not fields.get('Package'):
        continue
    if fields['Package'] not in {'com.theipos.camera','com.theipos.o2camera','com.theipos.dock'}:
        continue
    relative = fields['Filename'].removeprefix('./')
    if not re.fullmatch(r'[A-Za-z0-9_./+\-]+', relative) or '..' in relative.split('/') or relative.startswith('/'):
        raise ValueError('Unsafe package path')
    data = read(relative, 64*1024*1024)
    if hashlib.sha256(data).hexdigest() != fields['SHA256'] or len(data) != int(fields['Size']):
        raise ValueError('Package integrity mismatch')
    package_id = fields['Package']
    folder = 'Camera' if package_id.endswith(('.camera','.o2camera')) else 'Utility'
    published = folder + '/' + pathlib.PurePosixPath(relative).name
    fields['Filename'] = './' + published
    block = re.sub(r'^Filename: .+$', 'Filename: ./' + published, block, flags=re.M)
    blocks.append(block.strip())
    dest = out / published
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    packages.append(fields)
if not packages:
    raise ValueError('Empty source')
index = ('\n\n'.join(blocks) + '\n\n').encode('utf8')
(out / 'Packages').write_bytes(index)
(out / 'Packages.gz').write_bytes(gzip.compress(index, mtime=0))
(out / 'Packages.bz2').write_bytes(bz2.compress(index))
release = 'Origin: Nelora\nLabel: Nelora\nArchitectures: iphoneos-arm\nComponents: main\nDescription: Camera, Dock, Motion Blur and Glass for iOS 12 / Chimera\nSHA256:\n'
for name in ['Packages', 'Packages.gz', 'Packages.bz2']:
    data = (out / name).read_bytes()
    release += f' {hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'
(out / 'Release').write_text(release, encoding='utf8')
(out / '.nojekyll').touch()
(out / 'CydiaIcon.png').write_bytes(read('icons/nulora-motion.png'))
for folder in ['Camera', 'Utility', 'iOS26', 'Icons', 'Wallpapers']:
    (out / folder).mkdir(exist_ok=True)
    pathlib.Path(folder).mkdir(exist_ok=True)
for kind in ['camera', 'o2camera', 'dock']:
    (out / 'Icons' / f'nelora-{kind}.png').write_bytes(read(f'icons/nulora-{kind}.png'))
(out / 'Wallpapers' / 'README.md').write_text('Обои пока не добавлены.\n', encoding='utf8')
# Put the actual public DEBs and folders in GitHub Code as requested, not just in Actions artifacts.
for folder in ['Camera', 'Utility', 'iOS26', 'Icons', 'Wallpapers']:
    shutil.copytree(out / folder, folder, dirs_exist_ok=True)
for name in ['Packages', 'Packages.gz', 'Packages.bz2', 'Release', 'CydiaIcon.png', '.nojekyll']:
    shutil.copyfile(out / name, name)
# This is an APT source only. No website or catalogue HTML is published.
print(f'Published {len(packages)} verified packages')
