import functools
import time
import tracemalloc
import psutil
import logging


def track_metrics(metrics=("time", "memory", "cpu")):
    """Decorator to track specified metrics (time, memory, cpu) during function execution.
    The decorator logs the metrics using the provided logger or a default logger if none is provided.
    Args:
        metrics (tuple): Metrics to track. Options are "time", "memory", "cpu
        logger (logging.Logger): Logger instance to log the metrics. If None, uses a default logger.
    Usage:
        @track_metrics(metrics=("time", "memory", "cpu"), logger=dynamic_logger)
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
                    metrics_message += f"memory: {current / (1024 ** 2):.2f} MB (peak: {peak / (1024 ** 2):.2f} MB)"
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
