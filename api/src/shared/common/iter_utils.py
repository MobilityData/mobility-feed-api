from itertools import islice


def batched(iterable, n):
    """
    Batch an iterable into tuples of length `n`. The last batch may be shorter.

    Based on the implementation in more-itertools and will be built-in once we
    switch to Python 3.12+.
    """
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch
