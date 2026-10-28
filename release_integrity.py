"""Detect changes against the packaged manifest, not its authenticity."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from app_release import APP_VERSION

ROOT = Path(__file__).resolve().parent
MANIFEST = 'release-manifest.json'


def verify(root=ROOT):
    root = Path(root).resolve()
    errors = []
    try:
        path = root / MANIFEST
        if path.is_symlink() or path.stat().st_size > 100_000:
            raise ValueError()
        manifest = json.loads(path.read_text(encoding='utf-8'))
        files = manifest['files']
        if manifest['version'] != APP_VERSION or not isinstance(files, dict) or not 40 <= len(files) <= 300:
            raise ValueError()
        for name, expected in files.items():
            relative = PurePosixPath(name)
            file = root / name
            if (relative.is_absolute() or '..' in relative.parts or '\\' in name
                    or file.is_symlink() or not file.resolve().is_relative_to(root)
                    or not isinstance(expected, str) or len(expected) != 64):
                raise ValueError()
            if not file.is_file() or file.stat().st_size > 8_000_000:
                errors.append(name)
            elif hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                errors.append(name)
        for folder, patterns in ((root, ('*.py', '*.bat')), (root / 'web', ('*.js', '*.html', '*.css')), (root / 'tools', ('*.py', '*.cjs', '*.ps1'))):
            for pattern in patterns:
                for file in folder.glob(pattern):
                    if file.relative_to(root).as_posix() not in files:
                        errors.append(file.relative_to(root).as_posix())
        return {'verified': not errors, 'checkedFiles': len(files), 'changedFiles': sorted(set(errors)),
                'notice': 'Sumy sprawdzają zgodność z paczką, nie autentyczność wydawcy ani brak wirusów.'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'verified': False, 'checkedFiles': 0, 'changedFiles': [MANIFEST],
                'notice': 'Brak lub uszkodzony manifest wydania. Rozpakuj cały projekt ponownie.'}
