from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from .models import Automation


class JsonStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_path.write_text(json.dumps({"automations": []}, indent=2), encoding="utf-8")

    def _read_raw(self) -> dict[str, Any]:
        self._ensure_file()
        with self._lock:
            return json.loads(self.file_path.read_text(encoding="utf-8"))

    def _write_raw(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_automations(self) -> list[Automation]:
        payload = self._read_raw()
        return [Automation.from_dict(item) for item in payload.get("automations", [])]

    def save_automations(self, automations: list[Automation]) -> None:
        self._write_raw({"automations": [item.to_dict() for item in automations]})

    def get_automation(self, automation_id: str) -> Automation | None:
        for automation in self.list_automations():
            if automation.id == automation_id:
                return automation
        return None

    def upsert_automation(self, automation: Automation) -> None:
        automations = self.list_automations()
        for index, item in enumerate(automations):
            if item.id == automation.id:
                automations[index] = automation
                break
        else:
            automations.append(automation)
        self.save_automations(automations)

    def delete_automation(self, automation_id: str) -> bool:
        automations = self.list_automations()
        next_items = [item for item in automations if item.id != automation_id]
        if len(next_items) == len(automations):
            return False
        self.save_automations(next_items)
        return True

    def clear(self) -> None:
        """Hapus semua automation dari storage."""
        self.save_automations([])
