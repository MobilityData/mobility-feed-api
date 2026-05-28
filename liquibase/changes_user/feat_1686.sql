-- Issue #1686: Add is_registered_to_receive_api_announcements to app_user
-- This column tracks whether the user has opted into API announcement emails.
-- Replaces the equivalent field previously stored in Firebase Firestore.
ALTER TABLE app_user
    ADD COLUMN IF NOT EXISTS is_registered_to_receive_api_announcements BOOLEAN NOT NULL DEFAULT false;
