"""Versioned local configuration with atomic writes and explicit backup recovery."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

from platformdirs import user_config_path

from aim_tool.domain import LocationPreset, StepSpec, WorkflowSpec
from aim_tool.domain.models import Parameter


class ConfigError(ValueError):
    """Configuration is invalid or cannot be migrated safely."""


@dataclass(frozen=True)
class AppConfig:
    workflows: Mapping[str, WorkflowSpec] = field(default_factory=dict)
    locations: tuple[LocationPreset, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflows", MappingProxyType(dict(self.workflows)))


def _read_config(path: Path) -> AppConfig:
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ConfigError("Unsupported configuration schema")
        raw_workflows = data["workflows"]
        raw_locations = data["locations"]
        if not isinstance(raw_workflows, dict) or not isinstance(raw_locations, list):
            raise ConfigError("Invalid configuration structure")
        workflows: dict[str, WorkflowSpec] = {}
        for name, raw_workflow in raw_workflows.items():
            if not isinstance(name, str) or not isinstance(raw_workflow, dict):
                raise ConfigError("Invalid workflow entry")
            if raw_workflow.get("schema_version") != 1:
                raise ConfigError(f"Unsupported workflow schema: {name}")
            raw_steps = raw_workflow["steps"]
            if not isinstance(raw_steps, list):
                raise ConfigError("Invalid workflow steps")
            steps: list[StepSpec] = []
            for raw_step in raw_steps:
                if not isinstance(raw_step, dict) or not isinstance(raw_step.get("params"), dict):
                    raise ConfigError("Invalid component entry")
                params: dict[str, Parameter] = {}
                for key, value in raw_step["params"].items():
                    if (
                        not isinstance(key, str)
                        or value is not None
                        and not isinstance(value, str | int | float | bool)
                    ):
                        raise ConfigError("Invalid component parameter")
                    params[key] = value
                if (
                    not isinstance(raw_step.get("component_id"), str)
                    or type(raw_step.get("version")) is not int
                    or type(raw_step.get("enabled")) is not bool
                ):
                    raise ConfigError("Invalid component specification")
                steps.append(
                    StepSpec(
                        raw_step["component_id"],
                        raw_step["version"],
                        raw_step["enabled"],
                        params,
                    )
                )
            workflows[name] = WorkflowSpec(tuple(steps))
        locations: list[LocationPreset] = []
        for raw_location in raw_locations:
            if not isinstance(raw_location, dict):
                raise ConfigError("Invalid location entry")
            if (
                not isinstance(raw_location.get("name"), str)
                or type(raw_location.get("latitude")) not in {int, float}
                or type(raw_location.get("longitude")) not in {int, float}
                or raw_location.get("coordinate_system") != "WGS84"
                or raw_location.get("schema_version") != 1
            ):
                raise ConfigError("Invalid location specification")
            latitude = float(raw_location["latitude"])
            longitude = float(raw_location["longitude"])
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ConfigError("Location coordinates are out of range")
            locations.append(
                LocationPreset(
                    raw_location["name"],
                    latitude,
                    longitude,
                    UUID(raw_location["id"]),
                )
            )
        if len({location.id for location in locations}) != len(locations):
            raise ConfigError("Duplicate location ID")
        return AppConfig(workflows, tuple(locations))
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ConfigError):
            raise
        raise ConfigError(f"Invalid configuration at {path}: {error}") from error


def _serialize(config: AppConfig) -> str:
    if config.schema_version != 1:
        raise ConfigError("Unsupported configuration schema")
    if any(workflow.schema_version != 1 for workflow in config.workflows.values()):
        raise ConfigError("Unsupported workflow schema")
    data = {
        "schema_version": 1,
        "workflows": {
            name: {
                "schema_version": workflow.schema_version,
                "steps": [
                    {
                        "component_id": step.component_id,
                        "version": step.version,
                        "enabled": step.enabled,
                        "params": dict(step.params),
                    }
                    for step in workflow.steps
                ],
            }
            for name, workflow in config.workflows.items()
        },
        "locations": [
            {
                "id": str(location.id),
                "name": location.name,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "coordinate_system": location.coordinate_system,
                "schema_version": location.schema_version,
            }
            for location in config.locations
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_config_path("AutoImageMarkTool", "BG2FOU") / "config.json"
        self.backup = self.path.with_suffix(self.path.suffix + ".bak")

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        return _read_config(self.path)

    def save(self, config: AppConfig) -> None:
        content = _serialize(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".aim-config-",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            if self.path.exists():
                _read_config(self.path)
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=self.path.parent, prefix=".aim-backup-", delete=False
                ) as backup_file:
                    backup_temp = Path(backup_file.name)
                try:
                    shutil.copyfile(self.path, backup_temp)
                    os.replace(backup_temp, self.backup)
                finally:
                    backup_temp.unlink(missing_ok=True)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def restore_backup(self) -> AppConfig:
        if not self.backup.is_file():
            raise ConfigError("No configuration backup is available")
        restored = _read_config(self.backup)
        content = _serialize(restored)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".aim-restore-",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return restored

    def put_location(self, location: LocationPreset) -> None:
        current = self.load()
        by_id = {entry.id: entry for entry in current.locations}
        by_id[location.id] = location
        self.save(AppConfig(current.workflows, tuple(by_id.values())))

    def delete_location(self, location_id: UUID) -> None:
        current = self.load()
        remaining = tuple(entry for entry in current.locations if entry.id != location_id)
        self.save(AppConfig(current.workflows, remaining))
