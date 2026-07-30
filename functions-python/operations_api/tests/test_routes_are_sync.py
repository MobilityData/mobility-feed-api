#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#
"""Structural guard against the async/not-awaited route bug.

The generated FastAPI routers invoke the impl methods WITHOUT `await`
(``return BaseXApi.subclasses[0]().<method>(...)``). If an impl route method is
declared ``async`` it therefore returns an un-awaited coroutine, which FastAPI
cannot serialize -> HTTP 500 (ResponseValidationError) at runtime.

The unit tests call the impls directly and ``await`` them, so they never catch
this. This test asserts, purely by reflection (no DB, no server, milliseconds),
that every route-backing impl method -- and anything it wraps -- is synchronous.
"""
import inspect

import pytest

# Base classes declare the route methods; importing the impl modules registers
# each impl into ``Base.subclasses`` via ``__init_subclass__``.
from feeds_gen.apis.operations_api_base import BaseOperationsApi
from feeds_gen.apis.licenses_api_base import BaseLicensesApi
from feeds_gen.apis.users_api_base import BaseUsersApi
from feeds_operations.impl.feeds_operations_impl import OperationsApiImpl  # noqa: F401
from feeds_operations.impl.licenses_api_impl import LicensesApiImpl  # noqa: F401
from feeds_operations.impl.user_feature_flags_impl import UserFeatureFlagsApiImpl  # noqa: F401

BASES = (BaseOperationsApi, BaseLicensesApi, BaseUsersApi)


def _route_methods():
    """Yield (impl_class, method_name) for every route-backing method."""
    for base in BASES:
        assert base.subclasses, f"No impl registered for {base.__name__}"
        impl = base.subclasses[0]
        for name, _ in inspect.getmembers(base, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            yield impl, name


CASES = list(_route_methods())


def test_all_routes_discovered():
    # Sanity: all three routers contribute methods (guards against an import/registration regression).
    assert len(CASES) >= 19, f"Expected >= 19 route methods, found {len(CASES)}"


@pytest.mark.parametrize(
    "impl, method_name",
    CASES,
    ids=[f"{impl.__name__}.{name}" for impl, name in CASES],
)
def test_route_method_is_synchronous(impl, method_name):
    """A route method (and any function it wraps) must be a plain `def`."""
    fn = getattr(impl, method_name)
    seen = set()
    while fn is not None and id(fn) not in seen:
        seen.add(id(fn))
        assert not inspect.iscoroutinefunction(fn), (
            f"{impl.__name__}.{method_name} (or a function it wraps) is `async`. "
            "The generated router calls it without `await`, so it returns an "
            "un-awaited coroutine at runtime (HTTP 500). Make it a regular `def`."
        )
        fn = getattr(fn, "__wrapped__", None)
