"""Private local credential file; Windows DPAPI binds encryption to OS user."""
import base64
import json
import os
import tempfile
from pathlib import Path


def _windows(data,decrypt=False):
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    crypt=ctypes.windll.crypt32;kernel=ctypes.windll.kernel32
    crypt.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype=wintypes.BOOL
    crypt.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:ok=crypt.CryptProtectData(ctypes.byref(source),'Inwestapp OKX Demo',None,None,None,1,ctypes.byref(target))
    if not ok:raise ValueError('Nie udało się zabezpieczyć lub odczytać kluczy przez Windows DPAPI.')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)


def write(path,values):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(values).encode()
    if os.name=='nt':content=json.dumps({'protection':'windows-dpapi','payload':base64.b64encode(_windows(content)).decode()}).encode()
    else:path.parent.chmod(0o700)
    if path.is_symlink():raise ValueError('Prywatna konfiguracja nie może być dowiązaniem.')
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent)
    temp=Path(name)
    try:
        with os.fdopen(fd,'wb') as file:
            file.write(content);file.flush();os.fsync(file.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    if os.name!='nt':path.chmod(0o600)


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>64_000:raise ValueError('Nieprawidłowy prywatny plik konfiguracji.')
    if os.name!='nt' and path.stat().st_mode&0o077:raise ValueError('Prywatny plik kluczy wymaga uprawnień 0600.')
    value=json.loads(path.read_text())
    if value.get('protection')=='windows-dpapi':
        if os.name!='nt':raise ValueError('Klucze Windows wymagają tego samego użytkownika Windows; skonfiguruj je ponownie na serwerze.')
        value=json.loads(_windows(base64.b64decode(value['payload']),True))
    return value
