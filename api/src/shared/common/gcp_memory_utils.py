import os
import resource
import shutil
import logging

MB_MULTIPLIER = 1024**2


def find_tmpfs_mounts():
    """
    Returns a list of tmpfs mount points whose path contains 'in-memory',
    from /proc/mounts.
    """
    tmpfs_mounts = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2] == "tmpfs" and "in-memory" in parts[1]:
                    tmpfs_mounts.append(parts[1])
    except Exception as e:
        logging.error(f"Error reading /proc/mounts: {e}")
    return tmpfs_mounts


def get_memory_limit_cgroup_bytes():
    """
    Returns the memory limit for the process (in bytes) as set by cgroups, or None if not found.
    """
    try:
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
            limit_bytes = int(f.read())
            # If the limit is a very large number (e.g., 2**63), treat as unlimited
            if limit_bytes < (2**60):
                return limit_bytes
    except Exception:
        pass
    return None


def get_total_tmpfs_size_bytes():
    """
    Returns the total size (in bytes) of all tmpfs mounts whose path contains 'in-memory',
    or None if none found or all unlimited.
    """
    tmpfs_mounts = find_tmpfs_mounts()
    total_size = 0
    found = False
    for mount in tmpfs_mounts:
        if os.path.exists(mount):
            try:
                total, _, _ = shutil.disk_usage(mount)
                # If total is suspiciously large (>= 1 PB), treat as unlimited
                if total < 1 << 50:  # Ignore unlimited mounts
                    total_size += total
                    found = True
            except Exception as e:
                logging.error(f"Error getting disk usage for {mount}: {e}")
    if found:
        return total_size
    return None


def get_available_process_memory_bytes():
    """
    Returns the available memory for the process in bytes:
    total process memory limit (cgroup) minus the total size of all tmpfs
    filesystems whose path contains 'in-memory'. If any value is unlimited
    or not found, returns None.
    """
    mem_limit = get_memory_limit_cgroup_bytes()
    tmpfs_size = get_total_tmpfs_size_bytes()
    if mem_limit is None or tmpfs_size is None:
        logging.warning("Could not determine available process memory " "(limit or tmpfs size missing/unlimited).")
        return None
    available_bytes = mem_limit - tmpfs_size
    logging.info(
        "Process memory limit: %.2f MiB, total tmpfs size: %.2f MiB, available: %.2f MiB",
        mem_limit / MB_MULTIPLIER,
        tmpfs_size / MB_MULTIPLIER,
        available_bytes / MB_MULTIPLIER,
    )
    return available_bytes


def limit_gcp_memory():
    # Margin comes from env in megabytes (string), default 200 MiB
    memory_margin_str_mb = os.getenv("MEMORY_MARGIN_MB", "200")

    available_memory_bytes = get_available_process_memory_bytes()
    if not available_memory_bytes or available_memory_bytes <= 0:
        logging.info("Could not find the total memory of the process. Memory limit not set.")
        return

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

    memory_margin_bytes = memory_margin_mb * MB_MULTIPLIER if memory_margin_mb > 0 else 0
    logging.info(
        "Available memory: %.2f MiB, memory margin: %.2f MiB",
        available_memory_bytes / MB_MULTIPLIER,
        memory_margin_bytes / MB_MULTIPLIER,
    )
    mem_limit = available_memory_bytes - memory_margin_bytes
    if mem_limit <= 0:
        logging.warning(
            "Computed RLIMIT_AS <= 0 (%.2f MiB). Skipping setrlimit.",
            mem_limit / MB_MULTIPLIER,
        )
        return

    # Set RLIMIT_AS in bytes, log the limit in MiB
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    logging.info(
        "RLIMIT_AS set to %.2f MiB (raw: %d bytes)",
        mem_limit / MB_MULTIPLIER,
        mem_limit,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    available = get_available_process_memory_bytes()
    if available is not None:
        print(f"Available process memory: {available / MB_MULTIPLIER:.2f} MiB")
    else:
        print("Could not determine available process memory.")
