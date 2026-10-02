"""S2 local configuration and output safety tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from aim_tool.domain import LocationPreset, PhotoItem
from aim_tool.services.output import OutputError, commit_no_overwrite, output_path
from aim_tool.services.storage import AppConfig, ConfigError, ConfigStore
from aim_tool.services.watermark import WatermarkResources
from aim_tool.workflow.registry import preset


def test_config_restart_location_ids_and_explicit_backup_restore(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    workflow = preset("location_only")
    first = AppConfig({"my workflow": workflow})
    store.save(first)
    location_a = LocationPreset("同名地点", 24.5, 118.1)
    location_b = LocationPreset("同名地点", 25.0, 119.0)
    store.put_location(location_a)
    store.put_location(location_b)
    restarted = ConfigStore(store.path)
    loaded = restarted.load()
    assert loaded.workflows["my workflow"] == workflow
    assert {location.id for location in loaded.locations} == {location_a.id, location_b.id}
    restarted.delete_location(location_a.id)
    assert [location.id for location in restarted.load().locations] == [location_b.id]

    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        restarted.load()
    recovered = restarted.restore_backup()
    assert [location.id for location in recovered.locations] == [location_a.id, location_b.id]
    assert restarted.load() == recovered
    assert restarted.backup.is_file()


def test_reject_newer_config_schema_and_invalid_coordinate(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.path.write_text('{"schema_version": 2}', encoding="utf-8")
    with pytest.raises(ConfigError, match="Unsupported configuration schema"):
        store.load()
    with pytest.raises(ValueError, match="Invalid WGS84"):
        LocationPreset("bad", 91, 0)


def test_commit_never_overwrites_target(tmp_path: Path) -> None:
    temporary = tmp_path / "temp.jpg"
    target = tmp_path / "out.jpg"
    temporary.write_bytes(b"new")
    commit_no_overwrite(temporary, target)
    assert target.read_bytes() == b"new"
    assert not temporary.exists()
    another = tmp_path / "another.jpg"
    another.write_bytes(b"other")
    with pytest.raises(FileExistsError):
        commit_no_overwrite(another, target)
    assert target.read_bytes() == b"new"
    assert another.read_bytes() == b"other"


def test_output_symlink_to_source_dir_is_rejected(tmp_path: Path) -> None:
    source_root = tmp_path / "input"
    source_root.mkdir()
    source = source_root / "a.jpg"
    source.write_bytes(b"synthetic")
    alias = tmp_path / "output-alias"
    alias.symlink_to(source_root, target_is_directory=True)
    item = PhotoItem(source, source_root)
    with pytest.raises(OutputError, match="Output directory must differ"):
        output_path(item, preset("location_only"), alias)


def test_corrupt_current_config_cannot_replace_good_backup(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.save(AppConfig({"first": preset("location_only")}))
    store.save(AppConfig({"second": preset("watermark_only")}))
    healthy_backup = store.backup.read_bytes()
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        store.save(AppConfig())
    assert store.backup.read_bytes() == healthy_backup


def test_watermark_settings_corruption_does_not_overwrite_backup(
    tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    from aim_tool.services.storage import WatermarkSettings, WatermarkSettingsStore

    store = WatermarkSettingsStore(tmp_path / "settings.json")
    first = WatermarkSettings(synthetic_watermark_resources, {"font_size_pt": 24})
    store.save(first)
    store.save(WatermarkSettings(synthetic_watermark_resources, {"font_size_pt": 36}))
    assert store.load().params["font_size_pt"] == 36
    store.path.write_text("broken")
    with pytest.raises(ConfigError):
        store.load()
    with pytest.raises(ConfigError):
        store.save(first)
    assert store.path.read_text() == "broken"
    assert store.restore_backup().params["font_size_pt"] == 24
    assert store.load() == first
