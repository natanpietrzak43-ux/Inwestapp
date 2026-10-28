"""Maintainer tool: generate reviewed release file hashes before packaging."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_release import APP_VERSION


def build(root=ROOT):
    suffixes = {'.py', '.js', '.cjs', '.css', '.html', '.bat', '.ps1', '.service', '.timer', '.md', '.txt', '.yml'}
    files = {}
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if any(p.startswith('.') and p not in ('.github', '.gitignore', '.gitattributes') for p in relative.parts):
            continue
        if any(p in ('__pycache__', 'node_modules', 'private') for p in relative.parts):
            continue
        if file.is_file() and not file.is_symlink() and (file.suffix in suffixes or relative.as_posix() in ('.gitignore', '.gitattributes')):
            files[relative.as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    (root / 'release-manifest.json').write_text(json.dumps({'version': APP_VERSION, 'algorithm': 'sha256', 'files': files}, indent=2) + '\n', encoding='utf-8')
    return len(files)


if __name__ == '__main__':
    print('Manifest release files:', build())
