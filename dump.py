# dump.py
"""Собирает все файлы проекта в один txt для отправки."""
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = "project_dump.txt"

EXCLUDE_DIRS = {
    ".venv", "venv", "__pycache__", ".git",
    "data", "node_modules", ".idea", ".vscode",
}

EXCLUDE_FILES = {
    "project_dump.txt",
    "config/global.json",   # API-ключи
    "config.json",          # старый конфиг
    "bot.log",
}

INCLUDE_EXT = {
    ".py", ".json", ".txt", ".md", ".toml",
    ".ini", ".cfg", ".yml", ".yaml",
}


def _should_skip(path, name):
    # Пропускаем исключённые файлы
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    if rel in EXCLUDE_FILES:
        return True
    if name in EXCLUDE_FILES:
        return True

    # Пропускаем файлы с секретами
    if "config" in rel and rel.endswith("global.json"):
        return True

    # Только определённые расширения
    ext = os.path.splitext(name)[1].lower()
    if ext not in INCLUDE_EXT:
        return True

    return False


def _is_excluded_dir(path):
    parts = set(os.path.normpath(path).split(os.sep))
    return bool(parts & EXCLUDE_DIRS)


def main():
    lines = []
    lines.append(f"# PROJECT DUMP — {datetime.now().isoformat()}")
    lines.append(f"# ROOT: {ROOT}\n")

    count = 0
    total_bytes = 0
    skipped_secret = []

    for root, dirs, files in os.walk(ROOT):
        # Исключаем директории
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        if _is_excluded_dir(root):
            continue

        files.sort()
        for fname in files:
            if _should_skip(os.path.join(root, fname), fname):
                rel = os.path.relpath(os.path.join(root, fname), ROOT)
                if fname.endswith(".json") and "global" in fname:
                    skipped_secret.append(rel)
                continue

            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, ROOT)

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(fpath, "r", encoding="cp1251") as f:
                        content = f.read()
                except Exception:
                    continue
            except OSError:
                continue

            size = len(content)
            total_bytes += size

            lines.append("=" * 80)
            lines.append(f"### FILE: {rel}")
            lines.append(f"### SIZE: {size} bytes")
            lines.append("=" * 80)
            lines.append(content)
            lines.append("")
            count += 1

    lines.append("=" * 80)
    lines.append(f"### TOTAL: {count} files, {total_bytes} bytes")
    if skipped_secret:
        lines.append(f"### SKIPPED (secrets): {', '.join(skipped_secret)}")
    lines.append("=" * 80)

    out_path = os.path.join(ROOT, OUTPUT)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Готово: {OUTPUT}")
    print(f"  Файлов: {count}")
    print(f"  Размер: {total_bytes / 1024:.1f} KB")
    if skipped_secret:
        print(f"  Пропущено (секреты): {', '.join(skipped_secret)}")


if __name__ == "__main__":
    main()