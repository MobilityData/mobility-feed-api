import logging
import os
import shutil

from shared.helpers.logger import get_logger


class EphemeralOrDebugWorkdir:
    """Context manager similar to tempfile.TemporaryDirectory with debug + auto-clean.

    Behavior:
      - If DEBUG_WORKDIR env var is set (non-empty): that directory is created (if needed),
        returned, and never deleted nor cleaned.
      - Else: creates a temporary directory under the provided dir (or WORKDIR_ROOT env var),
        removes sibling directories older than a TTL (default 3600s / override via WORKDIR_MAX_AGE_SECONDS),
        and deletes the created directory on exit.

    Only directories whose names start with the fixed CLEANUP_PREFIX are considered for cleanup
    to avoid deleting unrelated folders that might exist under the same root.

    The final on-disk directory name always starts with the hardcoded prefix 'pmtiles_'.
    The caller-supplied prefix (if any) is appended verbatim after that.
    """

    CLEANUP_PREFIX = "pmtiles_"

    def __init__(
        self,
        dir: str | None = None,
        prefix: str | None = None,
        logger: logging.Logger | None = None,
    ):
        import tempfile

        self._debug_dir = os.getenv("DEBUG_WORKDIR") or None
        self._root = dir or os.getenv("WORKDIR_ROOT", "/tmp/in-memory")
        self._logger = logger or get_logger("Workdir")
        self._temp: tempfile.TemporaryDirectory[str] | None = None
        self.name: str

        os.makedirs(self._root, exist_ok=True)
        # 0 means just delete everything without looking at the file dates.
        self._ttl_seconds = int(os.getenv("WORKDIR_MAX_AGE_SECONDS", "0"))

        if self._debug_dir:
            os.makedirs(self._debug_dir, exist_ok=True)
            self.name = self._debug_dir
            return

        self._cleanup_old()

        # Simple prefix: fixed manager prefix + raw user prefix (if any)
        combined_prefix = self.CLEANUP_PREFIX + (prefix or "")

        self._temp = tempfile.TemporaryDirectory(dir=self._root, prefix=combined_prefix)
        self.name = self._temp.name

    def _cleanup_old(self):
        """
        Delete stale work directories created by this manager (names starting with CLEANUP_PREFIX)
        whose modification time is older than the configured TTL.
        """
        import time

        # If in debug mode, dont cleanup anything
        if self._debug_dir:
            return

        now = time.time()
        deleted_count = 0
        try:
            entries = list(os.scandir(self._root))
        except OSError as e:
            self._logger.warning("Could not scan workdir root %s: %s", self._root, e)
            return

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if not entry.name.startswith(self.CLEANUP_PREFIX):
                    continue
                try:
                    age = now - entry.stat(follow_symlinks=False).st_mtime
                except OSError:
                    continue
                if age > self._ttl_seconds:
                    shutil.rmtree(entry.path, ignore_errors=True)
                    deleted_count += 1
                    self._logger.warning(
                        "Removed expired workdir: %s age=%.0fs", entry.path, age
                    )
            except OSError as e:
                self._logger.warning("Failed to remove %s: %s", entry.path, e)

        if deleted_count:
            self._logger.info(
                "Cleanup removed %d expired workdirs from %s", deleted_count, self._root
            )

    def __enter__(self) -> str:  # Return path like TemporaryDirectory
        return self.name

    def __exit__(self, exc_type, exc, tb):
        if self._temp:
            self._temp.cleanup()
        return False  # do not suppress exceptions
