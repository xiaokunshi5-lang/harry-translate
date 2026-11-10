"""Record exact build package versions and official PyPI hashes; collect licenses."""
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parent
packages = sorted({(d.metadata['Name'], d.version) for d in metadata.distributions()})


def lock_package(item):
    name, version = item
    with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
        info = json.load(response)
    hashes = sorted({file['digests']['sha256'] for file in info['urls']})
    if not hashes:
        raise RuntimeError(f'No published hashes: {name}=={version}')
    return name + '==' + version + ' \\\n' + ' \\\n'.join('    --hash=sha256:' + value for value in hashes)


with ThreadPoolExecutor(max_workers=6) as pool:
    records = list(pool.map(lock_package, packages))
(root / 'requirements-windows.lock').write_text(
    '# Windows x64 / Python 3.12 build environment. Install using --require-hashes.\n'
    '--index-url https://pypi.org/simple\n' + '\n'.join(records) + '\n', encoding='utf-8')

licenses = root / 'licenses'
licenses.mkdir(exist_ok=True)
summary = []
for name, version in packages:
    dist = metadata.distribution(name)
    license_name = dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See upstream distribution'
    summary.append(f'{name} {version}\n{license_name}\n')
    for file in dist.files or []:
        path = Path(str(file))
        if '.dist-info' not in str(path) or not any(s in path.name.lower() for s in ('license', 'copying', 'notice')):
            continue
        source = Path(dist.locate_file(file))
        if source.is_file() and source.stat().st_size < 2_000_000:
            target = licenses / name / path.name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(source.read_bytes())
(licenses / 'THIRD_PARTY_NOTICES.txt').write_text(
    'Build environment dependency notices (includes build-only tools).\n'
    'PyInstaller license includes a commercial application bundling exception.\n\n' + '\n'.join(summary), encoding='utf-8')
print(f'Locked {len(packages)} packages with official hashes; dependency license texts collected.')
