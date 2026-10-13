"""Keep every NumPy vendor attribution when runtime FFT/DCT is frozen."""

import importlib.util
from pathlib import Path, PurePosixPath


def test_numpy_license_subtrees_do_not_collide(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "scripts" / "collect_licenses.py"
    spec = importlib.util.spec_from_file_location("frequency_license_collector", path)
    assert spec is not None and spec.loader is not None
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    collector.DESTINATION = tmp_path
    targets = [
        collector._installed_license_path("numpy", PurePosixPath(name))
        for name in (
            "numpy-2.5.3.dist-info/licenses/numpy/random/src/pcg64/LICENSE.md",
            "numpy-2.5.3.dist-info/licenses/numpy/random/src/philox/LICENSE.md",
            "numpy-2.5.3.dist-info/licenses/LICENSE.txt",
        )
    ]
    assert len(set(targets)) == 3
    assert all(target.is_relative_to(tmp_path) for target in targets)
    assert (
        collector._installed_license_path(
            "Pillow", PurePosixPath("pillow.dist-info/licenses/LICENSE")
        )
        == tmp_path / "Pillow" / "LICENSE"
    )
