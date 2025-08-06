import time
import tracemalloc
import psutil
import logging


def track_metrics(metrics=("time", "memory", "cpu"), logger=None):
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

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not logger:
                # Use a default logger if none is provided
                logger_instance = logging.getLogger(func.__name__)
                # handler = logging.StreamHandler()
                # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                # handler.setFormatter(formatter)
                # logger_instance.addHandler(handler)
                # logger_instance.setLevel(logging.DEBUG)
            else:
                logger_instance = logger

            process = psutil.Process()
            tracemalloc.start() if "memory" in metrics else None
            start_time = time.time() if "time" in metrics else None
            cpu_before = (
                process.cpu_percent(interval=None) if "cpu" in metrics else None
            )

            try:
                result = func(*args, **kwargs)
            except Exception as e:
                logger_instance.error(
                    f"Function '{func.__name__}' raised an exception: {e}"
                )
                raise
            finally:
                if "time" in metrics:
                    duration = time.time() - start_time
                    logger_instance.debug(
                        f"Function '{func.__name__}' executed in {duration:.2f} seconds."
                    )
                if "memory" in metrics:
                    current, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    logger_instance.debug(
                        f"Function '{func.__name__}' peak memory usage: {peak / (1024 ** 2):.2f} MB."
                    )
                if "cpu" in metrics:
                    cpu_after = process.cpu_percent(interval=None)
                    logger_instance.debug(
                        f"Function '{func.__name__}' CPU usage: {cpu_after - cpu_before:.2f}%."
                    )

            return result

        return wrapper

    return decorator
