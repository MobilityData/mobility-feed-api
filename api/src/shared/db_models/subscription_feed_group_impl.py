from typing import List

from shared.users_database_gen.sqlacodegen_models import NotificationSubscription as NotificationSubscriptionOrm
from user_service_gen.models.feed_subscription_summary import FeedSubscriptionSummary
from user_service_gen.models.subscription_feed_group import SubscriptionFeedGroup


class SubscriptionFeedGroupImpl(SubscriptionFeedGroup):
    """Implementation of the SubscriptionFeedGroup model.
    Builds a feed-centric view from the subscriptions that target one feed stable ID.
    """

    class Config:
        from_attributes = True

    @classmethod
    def from_subscriptions(
        cls,
        feed_stable_id: str,
        subs: List[NotificationSubscriptionOrm],
        feed_metadata: dict | None = None,
    ) -> SubscriptionFeedGroup:
        feed_metadata = feed_metadata or {}
        metadata = feed_metadata.get(feed_stable_id, {})
        return cls(
            feed_id=feed_stable_id,
            data_type=metadata.get("data_type"),
            provider=metadata.get("provider"),
            feed_name=metadata.get("feed_name"),
            subscriptions=[
                FeedSubscriptionSummary(
                    id=sub.id,
                    notification_id=sub.notification_type_id,
                    active=sub.active,
                    created_at=sub.created_at,
                )
                for sub in subs
            ],
        )
