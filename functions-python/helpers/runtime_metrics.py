import functools
import resource
import sys
import time
import tracemalloc
import psutil
import logging

MB = 1024**2


def _max_rss_bytes() -> int:
    """Peak resident set size of this process, in bytes.

    Note this is *resident*, while `limit_gcp_memory` caps *address space* via
    RLIMIT_AS. Virtual is always at least RSS and for a process mapping a database
    engine it is far larger, so sizing a container from RSS alone under-provisions it -
    which is why `vms` is reported beside this.

    `tracemalloc` only sees blocks Python itself allocated, so for a function whose
    heavy lifting happens in a C extension (DuckDB, for one) it reports the smallest
    consumer and misses the one that decides the instance's memory allocation. RSS
    covers both.

    This is the process high-water mark and it never resets, so on a warm instance it
    spans earlier requests too. It therefore over-reports rather than under-reports,
    which is the right direction for a number used to size a container.

    `ru_maxrss` is kilobytes on Linux and bytes on macOS.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def track_metrics(metrics=("time", "memory", "cpu")):
    """Decorator to track specified metrics (time, memory, cpu) during function execution.
    The decorator logs the metrics using the provided logger or a default logger if none is provided.
    Args:
        metrics (tuple): Metrics to track. Options are "time", "memory", "cpu".
    Usage:
        @track_metrics(metrics=("time", "memory", "cpu"))
        def example_function():
            data = [i for i in range(10**6)]  # Simulate work
            time.sleep(1)  # Simulate delay
            return sum(data)
    """

    def decorator(funct):
        @functools.wraps(funct)
        def wrapper(*args, **kwargs):
            logger = kwargs.get("logger")
            if not logger:
                # Use a default logger if none is provided
                logger = logging.getLogger(funct.__name__)

            process = psutil.Process()
            tracemalloc.start() if "memory" in metrics else None
            start_time = time.time() if "time" in metrics else None
            cpu_before = (
                process.cpu_percent(interval=None) if "cpu" in metrics else None
            )

            try:
                result = funct(*args, **kwargs)
            except Exception as e:
                logger.error(f"Function '{funct.__name__}' raised an exception: {e}")
                raise
            finally:
                metrics_message = ""
                if "time" in metrics:
                    duration = time.time() - start_time
                    metrics_message = f"time: {duration:.2f} seconds"
                if "memory" in metrics:
                    current, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    if metrics_message:
                        metrics_message += ", "
                    metrics_message += (
                        f"memory: {current / MB:.2f} MB (peak: {peak / MB:.2f} MB)"
                    )
                    # Kept beside the tracemalloc figures rather than replacing them, so
                    # the log line stays comparable with what is already in Cloud Logging.
                    try:
                        info = process.memory_info()
                        metrics_message += (
                            f", rss: {info.rss / MB:.2f} MB"
                            f" (process peak: {_max_rss_bytes() / MB:.2f} MB)"
                            f", vms: {info.vms / MB:.2f} MB"
                        )
                    except Exception as error:
                        logger.debug("Could not read memory info: %s", error)
                if "cpu" in metrics:
                    cpu_after = process.cpu_percent(interval=None)
                    if metrics_message:
                        metrics_message += ", "
                    metrics_message += f"cpu: {cpu_after - cpu_before:.2f}%"
                if len(metrics_message) > 0:
                    logger.info(
                        "Function metrics('%s'): %s", funct.__name__, metrics_message
                    )
            return result

        return wrapper

    return decorator
