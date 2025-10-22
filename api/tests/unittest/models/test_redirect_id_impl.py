import unittest

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
