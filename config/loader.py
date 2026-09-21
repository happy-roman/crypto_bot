# config/loader.py
import json
import logging
import os

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    "global": "global.json",
    "trading": "trading.json",
    "strategies": "strategies.json",
}


def _load(filename):
    path = os.path.join(_DIR, filename)
    if not os.path.exists(path):
        logger.warning(f"config/{filename} не найден")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка JSON в {filename}: {e}")
        return {}


def _save(filename, data):
    with open(os.path.join(_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Config:
    def __init__(self):
        self.global_ = _load(FILES["global"])
        self.trading = _load(FILES["trading"])
        self.strategies = _load(FILES["strategies"])

    def save(self, section):
        if section in FILES:
            _save(FILES[section], getattr(self, section))

    @property
    def grid(self):
        return self.strategies.get("grid", {})


CONFIG = Config()
