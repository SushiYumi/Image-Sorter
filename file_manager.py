"""File operations. Never overwrite an existing destination."""
import os
import re
import shutil
from pathlib import Path

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tif', '.tiff'}


def validate_name(name):
    if not name or not name.strip() or name in {'.', '..'}:
        raise ValueError('名稱不可空白。')
    if name.endswith((' ', '.')) or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        raise ValueError('名稱不可包含 <>:"/\\|?*，也不可用空格或句點結尾。')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('這是 Windows 保留名稱，請換一個名稱。')
    return name


def scan_folder(folder):
    folder = Path(folder).expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError('請選擇資料夾。')
    entries = sorted(folder.iterdir(), key=lambda p: p.name.casefold())
    images = [p for p in entries if not p.is_symlink() and p.is_file() and p.suffix.lower() in EXTENSIONS]
    categories = [p for p in entries if not p.is_symlink() and p.is_dir()]
    return folder, images, categories


def move_exact(source, destination):
    """Exclusive creation prevents accidental replacement, even on POSIX."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ValueError('來源圖片不存在或已被其他程式變更。')
    with source.open('rb') as reader:
        with destination.open('xb') as writer:
            try:
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
            except BaseException:
                writer.close()
                destination.unlink(missing_ok=True)
                raise
    try:
        shutil.copystat(source, destination)
        source.unlink()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def move_unique(source, folder, stem):
    validate_name(stem)
    source, folder = Path(source), Path(folder)
    destination = folder / (stem + source.suffix)
    if destination == source:
        return source
    count = 0
    while True:
        candidate = destination if count == 0 else folder / f'{stem}_{count}{source.suffix}'
        try:
            return move_exact(source, candidate)
        except FileExistsError:
            count += 1
