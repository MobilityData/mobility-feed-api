import functools
import logging
import resource
import sys
import threading
import time
import tracemalloc

import psutil

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


DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.25


class MemorySampler:
    """The high-water mark of this process's memory over a span of work.

    Neither reading available for free answers "how much did this piece of work need",
    which is the number a container is sized from:

    - `ru_maxrss` is a genuine peak, but it never resets. On a warm instance it carries
      whatever the previous request reached, so it over-reports an individual run.
    - `memory_info().vms` resets, but it is instantaneous. Read once at the end of a job
      that has already closed its database connection, it describes the quiet moment
      afterwards rather than the busy one in the middle, and under-reports badly.

    Polling answers it. The peak of a Parquet build falls inside a single table
    conversion, not between tables, so sampling at loop boundaries would miss it too.

    The thread is a daemon so a sampler that is never stopped cannot hold the process
    open, and every read is guarded: a measurement must never fail the work it measures.
    """

    def __init__(self, interval: float = DEFAULT_SAMPLE_INTERVAL_SECONDS):
        self.interval = interval
        self.peak_rss_bytes = 0
        self.peak_vms_bytes = 0
        self._stop = threading.Event()
        self._thread = None

    def _sample(self) -> None:
        try:
            info = psutil.Process().memory_info()
        except Exception:
            return
        self.peak_rss_bytes = max(self.peak_rss_bytes, info.rss)
        self.peak_vms_bytes = max(self.peak_vms_bytes, info.vms)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            self._sample()

    def start(self) -> "MemorySampler":
        """Begin sampling. Takes one reading immediately, so a span shorter than the
        interval still reports something rather than zero."""
        self._sample()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> dict:
        """Stop sampling and return the peaks, in the shape `record_attempt` reads."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            # Bounded so a wedged sampler cannot hold up the request it measured.
            thread.join(timeout=self.interval * 4)
        self._sample()
        return self.metrics()

    def metrics(self) -> dict:
        """The peaks so far. Zero means nothing could be read, which is reported as
        absent rather than as a measurement of nothing."""
        return {
            "peak_rss_bytes": self.peak_rss_bytes or None,
            "peak_vms_bytes": self.peak_vms_bytes or None,
        }

    def __enter__(self) -> "MemorySampler":
        return self.start()

    def __exit__(self, *_) -> None:
        self.stop()


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
