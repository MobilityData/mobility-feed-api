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


def test_debug_workdir_preserved(monkeypatch, tmp_path):
    # When DEBUG_WORKDIR is set, the provided debug dir should be used and not removed on exit
    debug_dir = tmp_path / "debug_workdir"
    # ensure non-existent prior to use
    if debug_dir.exists():
        for p in debug_dir.iterdir():
            if p.is_dir():
                os.rmdir(p)
        debug_dir.rmdir()

    monkeypatch.setenv("DEBUG_WORKDIR", str(debug_dir))
    # set a non-zero TTL to ensure cleanup would normally remove stale dirs
    monkeypatch.setenv("WORKDIR_MAX_AGE_SECONDS", "1")

    root = tmp_path / "workroot_debug"
    root.mkdir()

    # create a stale prefixed dir that would be removed if cleanup ran
    stale_dir = root / "pmtiles_stale_debug"
    stale_dir.mkdir()
    _backdate(stale_dir, 10)

    with EphemeralOrDebugWorkdir(dir=str(root)) as returned:
        # returned path should be the debug dir
        assert returned == str(debug_dir)
        assert Path(returned).exists()
        # stale prefixed dir should still exist because cleanup is skipped in debug mode
        assert stale_dir.exists()

    # After context exit, debug dir should still exist (not removed)
    assert debug_dir.exists()


def test_debug_mode_skips_cleanup(monkeypatch, tmp_path):
    # Ensure when DEBUG_WORKDIR is set, cleanup isn't performed on the root
    debug_dir = tmp_path / "debug2"
    monkeypatch.setenv("DEBUG_WORKDIR", str(debug_dir))
    monkeypatch.setenv("WORKDIR_MAX_AGE_SECONDS", "0")

    root = tmp_path / "workroot_debug2"
    root.mkdir()

    old_prefixed = root / "pmtiles_old"
    old_prefixed.mkdir()
    _backdate(old_prefixed, 1000)

    with EphemeralOrDebugWorkdir(dir=str(root)):
        # cleanup should be skipped, so old_prefixed still present
        assert old_prefixed.exists()
    # still present after exit
    assert old_prefixed.exists()
