# storage/json_store.py
import json
import os
import threading
import time

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)


class JsonStore:

    def __init__(self, name):
        self.path = os.path.join(DATA_DIR, f"{name}.json")
        self._lock = threading.RLock()
        if not os.path.exists(self.path):
            self._write([])

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, list) else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, self.path)

    def all(self):
        with self._lock:
            return self._read()

    def append(self, item):
        with self._lock:
            data = self._read()
            item = dict(item)
            item.setdefault("id", int(time.time() * 1000))
            item.setdefault("created_at", time.time())
            data.append(item)
            self._write(data)
            return item

    def update(self, item_id, patch):
        with self._lock:
            data = self._read()
            for row in data:
                if row.get("id") == item_id:
                    row.update(patch)
                    row["updated_at"] = time.time()
                    self._write(data)
                    return True
            return False

    def find(self, **filters):
        with self._lock:
            data = self._read()
            return [r for r in data
                    if all(r.get(k) == v for k, v in filters.items())]

    def find_one(self, **filters):
        rows = self.find(**filters)
        return rows[0] if rows else None
