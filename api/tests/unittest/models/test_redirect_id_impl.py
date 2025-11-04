import unittest
from unittest.mock import MagicMock, patch

from shared.database_gen.sqlacodegen_models import Redirectingid
from shared.database_gen.sqlacodegen_models import Feed
from shared.db_models.redirect_impl import RedirectImpl

redirect_orm = Redirectingid(
    source_id="source_id", target_id="target_id", redirect_comment="comment", target=Feed(stable_id="target_id")
)

expected_redirect = RedirectImpl(
    target_id="target_id",
    comment="comment",
)


class TestRedirectImpl(unittest.TestCase):
    """Test the `RedirectImpl` model."""

    def test_redirect_impl(self):
        assert RedirectImpl.from_orm(redirect_orm) == expected_redirect

    def test_redirect_impl_none_empty(self):
        """Test the `from_orm` method with empty and none value fields."""
        redirect_orm_empty = Redirectingid(
            source_id="", target_id="", redirect_comment=None, target=Feed(stable_id="target_id")
        )

        expected_redirect_empty = RedirectImpl(
            source_id="",
            target_id="target_id",
            comment=None,
        )

        assert RedirectImpl.from_orm(redirect_orm_empty) == expected_redirect_empty

    def test_redirect_impl_none(self):
        """Test the `from_orm` method with None."""
        assert RedirectImpl.from_orm(None) is None

    @patch("sqlalchemy.orm.Session")
    def test_to_orm_from_dict_none_or_missing_target(self, _mock_db):
        mock_session = MagicMock()
        assert RedirectImpl.to_orm_from_dict(None, db_session=mock_session) is None
        assert RedirectImpl.to_orm_from_dict({}, db_session=mock_session) is None
        # missing target_id
        assert RedirectImpl.to_orm_from_dict({"comment": "x"}, db_session=mock_session) is None
        mock_session.query.assert_not_called()

    @patch("sqlalchemy.orm.Session")
    def test_to_orm_from_dict_target_not_found(self, _mock_db):
        mock_session = MagicMock()
        # Configure chained calls: query().filter_by().first() -> None
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        payload = {"target_id": "stable-x", "comment": "moved"}
        assert RedirectImpl.to_orm_from_dict(payload, db_session=mock_session) is None
        mock_session.query.assert_called_once()

    @patch("sqlalchemy.orm.Session")
    def test_to_orm_from_dict_success(self, _mock_db):
        mock_session = MagicMock()
        # Mock a target Feed row with id and stable_id
        target = MagicMock()
        target.id = "feed-123"
        target.stable_id = "stable-x"
        mock_session.query.return_value.filter_by.return_value.first.return_value = target

        payload = {"target_id": "stable-x", "comment": "moved"}
        obj = RedirectImpl.to_orm_from_dict(payload, db_session=mock_session)

        from shared.database_gen.sqlacodegen_models import Redirectingid as RedirectingidOrm

        assert isinstance(obj, RedirectingidOrm)
        assert obj.target_id == "feed-123"
        assert obj.target is target
        assert obj.redirect_comment == "moved"
