"""Read-only local package verification. Does not scan or change Windows."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_release import APP_VERSION
import release_integrity

if __name__ == '__main__':
    result = release_integrity.verify()
    print('Inwestapp ' + APP_VERSION + ' | kontrola plikow')
    print('ZGODNE Z PACZKA' if result['verified'] else 'NIEZGODNE - nie uruchamiaj zmienionej kopii')
    print('Sprawdzone pliki:', result['checkedFiles'])
    for name in result['changedFiles']:print('Do ponownego pobrania:', name)
    print('To kontrola sum plikow, nie skaner antywirusowy. Korzystaj z aktualnego Microsoft Defender.')
    sys.exit(0 if result['verified'] else 2)
