import os
import tempfile
import time
from pathlib import Path

from src.main import EphemeralOrDebugWorkdir


def _backdate(path: Path, seconds_ago: int):
    t = time.time() - seconds_ago
    os.utime(path, (t, t))


def test_old_prefixed_dir_deleted_and_root_auto_removed(monkeypatch):
    monkeypatch.delenv("DEBUG_WORKDIR", raising=False)
    ttl = 30
    monkeypatch.setenv("WORKDIR_MAX_AGE_SECONDS", str(ttl))

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)

        stale_dir = root_path / "pmtiles_stale123"
        stale_dir.mkdir()
        _backdate(stale_dir, ttl + 300)

        keep_other = root_path / "unrelated_dir"
        keep_other.mkdir()

        fresh_prefixed = root_path / "pmtiles_fresh"
        fresh_prefixed.mkdir()
        _backdate(fresh_prefixed, 1)

        with EphemeralOrDebugWorkdir(dir=root) as new_dir:
            assert not stale_dir.exists()
            assert keep_other.exists()
            assert fresh_prefixed.exists()
            assert new_dir.startswith(root)
            assert Path(new_dir).exists()
            assert Path(new_dir).name.startswith("pmtiles_")

        # Temp workdir created by EphemeralOrDebugWorkdir should be gone
        assert not Path(new_dir).exists()

        # Root still exists inside the TemporaryDirectory context
        assert root_path.exists()

    # After exiting TemporaryDirectory, root is removed (Not strictly a test of the code, but check anyway)
    assert not root_path.exists()


def test_fresh_prefixed_dir_retained(monkeypatch, tmp_path):
    monkeypatch.delenv("DEBUG_WORKDIR", raising=False)
    monkeypatch.setenv("WORKDIR_MAX_AGE_SECONDS", "1000")

    root = tmp_path / "workroot2"
    root.mkdir()

    recent_dir = root / "pmtiles_recent"
    recent_dir.mkdir()
    _backdate(recent_dir, 10)  # Younger than TTL

    with EphemeralOrDebugWorkdir(dir=str(root)):
        assert recent_dir.exists()

    # Recent directory still present
    assert recent_dir.exists()
