# trading/migration.py
import logging
from storage.stores import positions_store

logger = logging.getLogger(__name__)


def migrate_position(pos):
    patch = {}
    if "avg_entry" not in pos:
        patch["avg_entry"] = pos.get("entry_price", 0)
    if "total_cost" not in pos:
        patch["total_cost"] = pos.get("entry_price", 0) * pos.get("amount", 0)
    if "tp_pct" not in pos:
        patch["tp_pct"] = 0.8
    if "grid_levels" not in pos:
        patch["grid_levels"] = []
    return patch


def migrate_all():
    fixed = 0
    for pos in positions_store.find(status="open"):
        patch = migrate_position(pos)
        if patch:
            positions_store.update(pos["id"], patch)
            fixed += 1
    if fixed:
        logger.info(f"Мигрировано позиций: {fixed}")
    return fixed
