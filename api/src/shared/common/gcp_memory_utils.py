import logging
import os
import resource
import shutil
import sys

MB_MULTIPLIER = 1024**2


def find_tmpfs_mounts(mount_point):
    """
    Check if the given mount_point is a tmpfs filesystem in /proc/mounts.

    Args:
        mount_point: The mount point path to check (e.g., "/tmp/in-memory")

    Returns:
        True if mount_point is found as a tmpfs filesystem, False otherwise.
    """

    # Check if we're on Linux (only Linux has /proc/mounts for tmpfs detection)
    if not os.path.exists("/proc/mounts"):
        logging.debug(f"Not on Linux (platform: {sys.platform}). tmpfs detection not available.")
        return []

    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == mount_point:
                    if parts[2] == "tmpfs":
                        return True
                    else:
                        logging.warning(f"{mount_point} is not a tmpfs filesystem (found: {parts[2]})")
                        return False
    except Exception as e:
        logging.error(f"Error reading /proc/mounts: {e}")
        return False
    logging.warning(f"{mount_point} not found in /proc/mounts")
    return False


def get_memory_limit_cgroup_bytes():
    """
    Returns the memory limit for the process (in bytes) as set by cgroups, or None if not found.
    Note that this value includes any in-memory file systems.
    Tries cgroup v1 first, then falls back to cgroup v2.
    """
    # cgroup v1
    try:
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
            limit_bytes = int(f.read())
            if limit_bytes < (2**60):
                return limit_bytes
    except Exception as e:
        logging.error("cgroup v1 memory limit not available: %s", e)

    # cgroup v2 fallback ("max" means unlimited)
    try:
        with open("/sys/fs/cgroup/memory.max", "r") as f:
            value = f.read().strip()
            if value != "max":
                return int(value)
    except Exception as e:
        logging.error("cgroup v2 memory limit not available: %s", e)

    return None


def get_total_tmpfs_size_bytes(mount_point):
    """
    Returns the size (in bytes) of the tmpfs at the given mount_point,
    or None if not found or not a tmpfs.

    Args:
        mount_point: The mount point path to check (e.g., "/tmp/in-memory")
    """
    if not find_tmpfs_mounts(mount_point):
        return None
    try:
        total, _, _ = shutil.disk_usage(mount_point)
        return total
    except Exception as e:
        logging.error(f"Error getting disk usage for {mount_point}: {e}")
        return None


def get_available_process_memory_bytes(mount_point):
    """
    Returns the available memory for the process in bytes:
    total process memory limit (cgroup) minus the size of the tmpfs
    filesystem at the given mount point.

    Args:
        mount_point: The tmpfs mount point path (e.g., "/tmp/in-memory")

    Returns:
        Available process memory in bytes, or None if not determinable.
    """
    mem_limit = get_memory_limit_cgroup_bytes()
    tmpfs_size = get_total_tmpfs_size_bytes(mount_point)
    if mem_limit is None or tmpfs_size is None:
        logging.warning("Could not determine available process memory (limit or tmpfs size missing/unlimited).")
        return None
    available_bytes = mem_limit - tmpfs_size
    logging.info(
        "Process memory limit: %.2f MiB, total tmpfs size: %.2f MiB, available: %.2f MiB",
        mem_limit / MB_MULTIPLIER,
        tmpfs_size / MB_MULTIPLIER,
        available_bytes / MB_MULTIPLIER,
    )
    return available_bytes


def limit_gcp_memory(mount_point):
    """
    Set memory limits for the process to prevent OOM kills in GCP Cloud Run/Functions.

    In GCP containerized environments, the cgroup memory limit includes both process memory
    and tmpfs (in-memory filesystem) usage. To prevent the kernel from OOM-killing the process,
    this function:
    1. Calculates available process memory (cgroup limit - tmpfs size)
    2. Subtracts a safety margin (default 200 MiB)
    3. Sets RLIMIT_AS to this value

    This causes Python to raise MemoryError before hitting the cgroup hard limit.
    The safety margin reserves enough headroom so that after MemoryError is raised,
    Python can still allocate the memory needed to unwind the stack, run exception
    handlers, log the error, send an HTTP response, and shut down gracefully.

    Args:
        mount_point: The tmpfs mount point path to check (e.g., "/tmp/in-memory")

    Environment Variables:
        MEMORY_MARGIN_MB: Safety margin in megabytes (default: 200)
    """
    # Get the memory margin from environment variable (default: 200 MiB)
    memory_margin_str_mb = os.getenv("MEMORY_MARGIN_MB", "200")

    # Calculate available memory: cgroup limit - tmpfs size
    available_memory_bytes = get_available_process_memory_bytes(mount_point)
    if not available_memory_bytes or available_memory_bytes <= 0:
        logging.info("Could not find the total memory of the process. Memory limit not set.")
        return

    # Parse and validate the memory margin
    memory_margin_mb = 200
    if memory_margin_str_mb:
        try:
            memory_margin_mb = int(memory_margin_str_mb)
        except ValueError as err:
            logging.error(
                "Invalid MEMORY_MARGIN_MB value: %s. Using default of 200MB. Error: %s",
                memory_margin_str_mb,
                err,
            )

    # Convert margin to bytes and calculate final memory limit
    memory_margin_bytes = memory_margin_mb * MB_MULTIPLIER if memory_margin_mb > 0 else 0
    logging.info(
        "Available memory: %.2f MiB, memory margin: %d MiB",
        available_memory_bytes / MB_MULTIPLIER,
        memory_margin_mb,
    )

    # Subtract safety margin so Python has breathing room to handle MemoryError
    # (stack unwinding, logging, sending HTTP response, graceful shutdown)
    mem_limit = available_memory_bytes - memory_margin_bytes
    if mem_limit <= 0:
        logging.warning(
            "Computed RLIMIT_AS <= 0 (%.2f MiB). Skipping setrlimit.",
            mem_limit / MB_MULTIPLIER,
        )
        return

    # Set RLIMIT_AS (address space limit) to prevent OOM kills
    # When this limit is exceeded, Python will raise MemoryError instead of being killed
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    logging.info("RLIMIT_AS set to %.2f MiB", mem_limit / MB_MULTIPLIER)
