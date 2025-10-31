import unittest
from datetime import datetime

from shared.db_models.feed_related_link_impl import FeedRelatedLinkImpl
from shared.database_gen.sqlacodegen_models import Feedrelatedlink


class TestFeedRelatedLinkImpl(unittest.TestCase):
    """Tests for FeedRelatedLinkImpl.from_orm and .to_orm_from_dict"""

    def test_from_orm_all_fields(self):
        created = datetime(2024, 1, 2, 3, 4, 5)
        orm = Feedrelatedlink(
            feed_id="feed-1",
            code="docs",
            url="https://example.com/docs",
            description="Documentation",
            created_at=created,
        )
        expected = FeedRelatedLinkImpl(
            code="docs",
            url="https://example.com/docs",
            description="Documentation",
            created_at=created,
        )

        result = FeedRelatedLinkImpl.from_orm(orm)
        assert result == expected

    def test_from_orm_none(self):
        assert FeedRelatedLinkImpl.from_orm(None) is None

    def test_to_orm_from_dict_none_empty(self):
        assert FeedRelatedLinkImpl.to_orm_from_dict(None) is None
        assert FeedRelatedLinkImpl.to_orm_from_dict({}) is None

    def test_to_orm_from_dict_valid(self):
        data = {
            "code": "home",
            "url": "https://example.com",
            "description": "Homepage",
        }
        obj = FeedRelatedLinkImpl.to_orm_from_dict(data)

        assert isinstance(obj, Feedrelatedlink)
        assert obj.code == "home"
        assert obj.url == "https://example.com"
        assert obj.description == "Homepage"

    def test_to_orm_from_dict_extra_keys_ignored(self):
        data = {
            "code": "api",
            "url": "https://api.example.com",
            "description": "API",
            "ignored": "x",
        }
        obj = FeedRelatedLinkImpl.to_orm_from_dict(data)

        assert isinstance(obj, Feedrelatedlink)
        assert obj.code == "api"
        assert obj.url == "https://api.example.com"
        assert obj.description == "API"
