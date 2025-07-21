import pytest
from unittest.mock import MagicMock
from shared.database_gen.sqlacodegen_models import Redirectingid, Gtfsfeed
from feeds_operations_gen.models.redirect import Redirect
from feeds_operations.impl.models.redirect_impl import RedirectImpl


def test_from_orm():
    redirecting_id = Redirectingid(
        target=MagicMock(stable_id="target_stable_id"), redirect_comment="Test comment"
    )
    result = RedirectImpl.from_orm(redirecting_id)
    assert result.target_id == "target_stable_id"
    assert result.comment == "Test comment"


def test_from_orm_none():
    result = RedirectImpl.from_orm(None)
    assert result is None


def test_to_orm():
    redirect = Redirect(target_id="target_stable_id", comment="Test comment")
    source_feed = Gtfsfeed(id=1, data_type="gtfs")
    target_feed = Gtfsfeed(id=2, stable_id="target_stable_id")
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = target_feed
    result = RedirectImpl.to_orm(redirect, source_feed, session)
    assert result.source_id == 1
    assert result.target_id == 2
    assert result.redirect_comment == "Test comment"


def test_to_orm_invalid_source():
    redirect = Redirect(target_id="target_stable_id", comment="Test comment")
    session = MagicMock()

    with pytest.raises(
        ValueError, match="Invalid source object or source.id is not set"
    ):
        RedirectImpl.to_orm(redirect, None, session)


def test_to_orm_invalid_target():
    redirect = Redirect(target_id="target_stable_id", comment="Test comment")
    source_feed = Gtfsfeed(id=1, data_type="gtfs")
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(
        ValueError, match="Invalid target_feed object or target_feed.id is not set"
    ):
        RedirectImpl.to_orm(redirect, source_feed, session)
