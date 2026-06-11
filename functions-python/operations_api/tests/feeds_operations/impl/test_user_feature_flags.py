#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import HTTPException

from feeds_operations.impl.user_feature_flags_impl import UserFeatureFlagsApiImpl
from feeds_gen.models.create_feature_flag_request import CreateFeatureFlagRequest
from feeds_gen.models.feature_flag_assignment import FeatureFlagAssignment
from feeds_gen.models.patch_user_feature_flags_request import (
    PatchUserFeatureFlagsRequest,
)
from feeds_gen.models.update_feature_flag_request import UpdateFeatureFlagRequest
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    FeatureFlag as FeatureFlagORM,
    UserFeatureFlag,
)

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _make_flag(
    flag_id="beta_editor",
    name="Beta Editor",
    description="Enables the beta editor",
    value_type="boolean",
    default_value=False,
    disabled=False,
) -> FeatureFlagORM:
    return FeatureFlagORM(
        id=flag_id,
        name=name,
        description=description,
        value_type=value_type,
        default_value=default_value,
        disabled=disabled,
        created_at=FIXED_NOW,
    )


def _make_uff(flag: FeatureFlagORM, user_id="uid-1", value=None) -> UserFeatureFlag:
    """Creates a UserFeatureFlag association object with the feature_flag pre-loaded."""
    uff = UserFeatureFlag(user_id=user_id, feature_flag_id=flag.id, value=value)
    uff.feature_flag = flag
    return uff


def _make_user(
    user_id="uid-1", email="user@example.com", user_feature_flags=None
) -> AppUser:
    user = AppUser(id=user_id, email=email, created_at=FIXED_NOW, updated_at=FIXED_NOW)
    user.user_feature_flags = (
        user_feature_flags if user_feature_flags is not None else []
    )
    return user


def _mock_query(session, result, flags=None):
    """Configure session.query to dispatch per model.

    `result` is the AppUser query result (list, single object, or None).
    `flags` is the list returned for the all-flags FeatureFlag query.
    """
    flags = flags if flags is not None else []

    def _build(value):
        mock_q = MagicMock()
        mock_q.options.return_value = mock_q
        mock_q.filter_by.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.offset.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.filter.return_value = mock_q
        mock_q.all.return_value = (
            value if isinstance(value, list) else [value] if value else []
        )
        mock_q.first.return_value = (
            value if not isinstance(value, list) else (value[0] if value else None)
        )
        return mock_q

    user_q = _build(result)
    flags_q = _build(flags)
    session.query.side_effect = lambda model: (
        flags_q if model is FeatureFlagORM else user_q
    )
    return user_q


class TestGetOperationsUsers(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_returns_all_users_when_no_query(self):
        users = [_make_user("uid-1"), _make_user("uid-2", email="b@b.com")]
        _mock_query(self.session, users)

        result = self.api.get_operations_users(db_session=self.session)

        self.assertEqual(len(result), 2)

    def test_returns_empty_list_when_no_users(self):
        _mock_query(self.session, [])

        result = self.api.get_operations_users(db_session=self.session)

        self.assertEqual(result, [])

    def test_includes_all_flags_with_user_override(self):
        flag = _make_flag()
        user = _make_user(user_feature_flags=[_make_uff(flag, value=True)])
        _mock_query(self.session, [user], flags=[flag])

        result = self.api.get_operations_users(db_session=self.session)

        self.assertEqual(len(result[0].features), 1)
        self.assertEqual(result[0].features[0].feature_flag_id, "beta_editor")
        self.assertEqual(result[0].features[0].user_value, True)

    def test_returns_all_flags_with_defaults_when_user_has_none(self):
        flag = _make_flag(default_value=False)
        user = _make_user(user_feature_flags=[])
        _mock_query(self.session, [user], flags=[flag])

        result = self.api.get_operations_users(db_session=self.session)

        self.assertEqual(len(result[0].features), 1)
        self.assertEqual(result[0].features[0].feature_flag_id, "beta_editor")
        self.assertEqual(result[0].features[0].default_value, False)
        self.assertIsNone(result[0].features[0].user_value)


class TestGetOperationsUser(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_returns_user_with_flags(self):
        flag = _make_flag()
        user = _make_user(user_feature_flags=[_make_uff(flag, value=True)])
        _mock_query(self.session, user, flags=[flag])

        result = self.api.get_operations_user("uid-1", db_session=self.session)

        self.assertEqual(result.id, "uid-1")
        self.assertEqual(len(result.features), 1)
        self.assertEqual(result.features[0].feature_flag_id, "beta_editor")
        self.assertEqual(result.features[0].user_value, True)

    def test_returns_all_flags_with_defaults_when_user_has_none(self):
        flag = _make_flag(default_value=False)
        user = _make_user(user_feature_flags=[])
        _mock_query(self.session, user, flags=[flag])

        result = self.api.get_operations_user("uid-1", db_session=self.session)

        self.assertEqual(len(result.features), 1)
        self.assertEqual(result.features[0].default_value, False)
        self.assertIsNone(result.features[0].user_value)

    def test_raises_404_when_user_not_found(self):
        _mock_query(self.session, None)

        with self.assertRaises(HTTPException) as ctx:
            self.api.get_operations_user("missing", db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 404)


class TestListFeatureFlags(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_returns_empty_list(self):
        _mock_query(self.session, [])

        result = self.api.list_feature_flags(db_session=self.session)

        self.assertEqual(result, [])

    def test_returns_all_flags(self):
        flags = [_make_flag("beta_editor"), _make_flag("dark_mode", name="Dark Mode")]
        _mock_query(self.session, [], flags=flags)

        result = self.api.list_feature_flags(db_session=self.session)

        self.assertEqual(len(result), 2)
        ids = [f.id for f in result]
        self.assertIn("beta_editor", ids)
        self.assertIn("dark_mode", ids)


class TestCreateFeatureFlag(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_creates_flag_successfully(self):
        self.session.get.return_value = None  # no existing flag

        req = CreateFeatureFlagRequest(
            id="new_flag",
            name="New Flag",
            description="A new flag",
            value_type="boolean",
            default_value=False,
        )
        result = self.api.create_feature_flag(req, db_session=self.session)

        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        self.assertEqual(result.id, "new_flag")
        self.assertEqual(result.name, "New Flag")
        self.assertEqual(result.value_type, "boolean")
        self.assertFalse(result.disabled)

    def test_creates_disabled_flag(self):
        self.session.get.return_value = None

        req = CreateFeatureFlagRequest(
            id="hidden_flag",
            value_type="boolean",
            default_value=False,
            disabled=True,
        )
        result = self.api.create_feature_flag(req, db_session=self.session)

        added_flag = self.session.add.call_args[0][0]
        self.assertTrue(added_flag.disabled)
        self.assertTrue(result.disabled)

    def test_raises_409_when_flag_already_exists(self):
        self.session.get.return_value = _make_flag("existing")

        req = CreateFeatureFlagRequest(
            id="existing",
            value_type="boolean",
            default_value=False,
        )
        with self.assertRaises(HTTPException) as ctx:
            self.api.create_feature_flag(req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 409)
        self.session.add.assert_not_called()

    def test_raises_422_when_default_value_mismatches_value_type(self):
        self.session.get.return_value = None

        req = CreateFeatureFlagRequest(
            id="bad_flag",
            value_type="numeric",
            default_value="not a number",
        )
        with self.assertRaises(HTTPException) as ctx:
            self.api.create_feature_flag(req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 422)
        self.session.add.assert_not_called()

    def test_creates_typed_values(self):
        self.session.get.return_value = None
        cases = [
            ("boolean", True),
            ("string", "hello"),
            ("numeric", 42),
            ("array", [1, 2, 3]),
            ("json", {"k": "v"}),
        ]
        for value_type, value in cases:
            with self.subTest(value_type=value_type):
                req = CreateFeatureFlagRequest(
                    id=f"flag_{value_type}",
                    value_type=value_type,
                    default_value=value,
                )
                result = self.api.create_feature_flag(req, db_session=self.session)
                self.assertEqual(result.value_type, value_type)

    def test_rejects_bool_for_numeric(self):
        self.session.get.return_value = None

        req = CreateFeatureFlagRequest(
            id="num_flag",
            value_type="numeric",
            default_value=True,
        )
        with self.assertRaises(HTTPException) as ctx:
            self.api.create_feature_flag(req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 422)


class TestUpdateFeatureFlag(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_updates_name_and_description(self):
        flag = _make_flag("beta_editor", name="Old Name", description="Old desc")
        self.session.get.return_value = flag

        req = UpdateFeatureFlagRequest(name="New Name", description="New desc")
        result = self.api.update_feature_flag(
            "beta_editor", req, db_session=self.session
        )

        self.assertEqual(result.name, "New Name")
        self.assertEqual(result.description, "New desc")
        self.session.flush.assert_called_once()

    def test_partial_update_leaves_other_fields(self):
        flag = _make_flag("beta_editor", name="Keep Me", description="Keep this too")
        self.session.get.return_value = flag

        req = UpdateFeatureFlagRequest(name="Updated Name")
        result = self.api.update_feature_flag(
            "beta_editor", req, db_session=self.session
        )

        self.assertEqual(result.name, "Updated Name")
        self.assertEqual(result.description, "Keep this too")

    def test_raises_404_when_flag_not_found(self):
        self.session.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self.api.update_feature_flag(
                "missing", UpdateFeatureFlagRequest(), db_session=self.session
            )

        self.assertEqual(ctx.exception.status_code, 404)

    def test_updates_disabled_flag(self):
        flag = _make_flag("beta_editor", disabled=False)
        self.session.get.return_value = flag

        req = UpdateFeatureFlagRequest(disabled=True)
        result = self.api.update_feature_flag(
            "beta_editor", req, db_session=self.session
        )

        self.assertTrue(flag.disabled)
        self.assertTrue(result.disabled)

    def test_updates_default_value_when_type_matches(self):
        flag = _make_flag("beta_editor", value_type="numeric", default_value=1)
        self.session.get.return_value = flag

        req = UpdateFeatureFlagRequest(default_value=99)
        result = self.api.update_feature_flag(
            "beta_editor", req, db_session=self.session
        )

        self.assertEqual(result.default_value, 99)

    def test_raises_422_when_default_value_mismatches_existing_type(self):
        flag = _make_flag("beta_editor", value_type="numeric", default_value=1)
        self.session.get.return_value = flag

        req = UpdateFeatureFlagRequest(default_value="not a number")
        with self.assertRaises(HTTPException) as ctx:
            self.api.update_feature_flag("beta_editor", req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 422)


class TestDeleteFeatureFlag(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def test_deletes_existing_flag(self):
        flag = _make_flag("beta_editor")
        self.session.get.return_value = flag

        result = self.api.delete_feature_flag("beta_editor", db_session=self.session)

        self.assertIsNone(result)
        self.session.delete.assert_called_once_with(flag)
        self.session.flush.assert_called_once()

    def test_raises_404_when_flag_not_found(self):
        self.session.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            self.api.delete_feature_flag("missing", db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 404)
        self.session.delete.assert_not_called()


class TestPatchUserFeatureFlags(unittest.TestCase):
    def setUp(self):
        self.api = UserFeatureFlagsApiImpl()
        self.session = MagicMock()

    def _setup_flags_query(self, flag_ids):
        """Make session.query(FeatureFlagORM.id).filter(...).all() return rows for given IDs."""
        mock_rows = [MagicMock(id=fid) for fid in flag_ids]
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        mock_q.all.return_value = mock_rows
        self.session.query.side_effect = lambda model: (
            mock_q if model is FeatureFlagORM.id else self.session.query(model)
        )
        return mock_q

    def test_raises_404_when_user_not_found(self):
        _mock_query(self.session, None)

        req = PatchUserFeatureFlagsRequest(assignments=[])
        with self.assertRaises(HTTPException) as ctx:
            self.api.patch_user_feature_flags("missing", req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_raises_404_when_flag_not_found(self):
        user = _make_user(user_feature_flags=[])

        def query_side_effect(model):
            mock_q = MagicMock()
            mock_q.options.return_value = mock_q
            mock_q.filter_by.return_value = mock_q
            mock_q.first.return_value = user
            mock_q.filter.return_value = mock_q
            mock_q.all.return_value = []  # no flags found
            return mock_q

        self.session.query.side_effect = query_side_effect

        req = PatchUserFeatureFlagsRequest(
            assignments=[FeatureFlagAssignment(feature_flag_id="nonexistent")]
        )
        with self.assertRaises(HTTPException) as ctx:
            self.api.patch_user_feature_flags("uid-1", req, db_session=self.session)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("nonexistent", ctx.exception.detail)

    def test_clears_flags_when_empty_list_provided(self):
        flag = _make_flag()
        user = _make_user(user_feature_flags=[_make_uff(flag)])

        mock_q = MagicMock()
        mock_q.options.return_value = mock_q
        mock_q.filter_by.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.first.return_value = user
        mock_q.all.return_value = []  # all-flags query returns no flags
        self.session.query.return_value = mock_q

        req = PatchUserFeatureFlagsRequest(assignments=[])
        self.api.patch_user_feature_flags("uid-1", req, db_session=self.session)

        # delete() should be called on the query to clear all assignments
        mock_q.delete.assert_called_once()
        self.session.add_all.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
