import logging
import traceback
import uuid
from typing import Optional, Type, Callable, Dict

from sqlalchemy.orm import Session
import pandas as pd
import os
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gtfsfeed, Externalid, Redirectingid, Gtfsrealtimefeed, Gtfsdataset
from shared.common.locations_utils import create_or_get_location
from tasks.data_import.data_import_utils import _get_or_create_feed, _get_or_create_entity_type, get_feed

logger = logging.getLogger(__name__)


def _safe_split(val: Optional[str], sep: str = " | ") -> list[str]:
    if pd.isna(val) or val is None:
        return []
    return [part.strip() for part in str(val).split(sep) if part and str(part).strip()]


def _process_feeds(
        db_session: Session,
        csv_filename: str,
        model_cls: Type,  # Gtfsfeed or Gtfsrealtimefeed
        feed_kind: str,  # 'gtfs' or 'gtfs_rt'
        dry_run: bool,
        on_is_new: Optional[Callable[[Session, object, pd.Series], None]] = None,  # hook for extras
) -> Dict[str, int | str]:
    """Generic CSV->Feed loader for TransitFeeds imports."""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), csv_filename)
        logger.info("Loading %s feeds from CSV: %s (dry_run=%s)", feed_kind.upper(), csv_path, dry_run)
        df = pd.read_csv(csv_path)
        logger.debug("CSV loaded: %d rows found for %s.", len(df), feed_kind.upper())

        total_processed = total_created = total_updated = 0

        for idx, row in df.iterrows():
            feed_stable_id = row['Mobility Database Feed ID']
            logger.debug("[%s][%d/%d] Processing feed_stable_id=%s", feed_kind.upper(), idx + 1, len(df), feed_stable_id)

            feed, is_new = _get_or_create_feed(db_session, model_cls, feed_stable_id, feed_kind, is_official=False)
            feed.status = 'deprecated'  # All TransitFeeds imports are deprecated by default
            logger.info("[%s] %s feed %s", feed_kind.upper(), "Creating" if is_new else "Updating", feed_stable_id)

            # Fields common to GTFS & GTFS-RT (set on creation only)
            if is_new:
                feed.name = row['Feed Name']
                feed.externalids = [
                    Externalid(source='transitfeeds', associated_id=row['External Feed ID'])
                ]
                feed.provider = row['Provider']
                feed.producer_url = row['Producer URL']
                logger.debug("[%s] Initialized new feed fields for %s (name=%s, provider=%s)",
                             feed_kind.upper(), feed_stable_id, feed.name, feed.provider)

                # Extra RT-only or type-specific initialization
                if on_is_new is not None:
                    try:
                        on_is_new(db_session, feed, row)
                        logger.debug("[%s] on_is_new callback executed for %s", feed_kind.upper(), feed_stable_id)
                    except Exception as e:
                        logger.exception("[%s] on_is_new callback failed for %s: %s", feed_kind.upper(), feed_stable_id, e)
                        raise

            # Redirects (shared)
            redirect_ids = _safe_split(row.get('Redirects'))
            if redirect_ids:
                feed.redirectingids.clear()
                logger.info("[%s] Set %d redirecting ids for %s", feed_kind.upper(), len(redirect_ids), feed_stable_id)
            logger.debug("[%s] %s redirect ids parsed: %s", feed_kind.upper(), feed_stable_id, redirect_ids)
            try:
                for target_id in redirect_ids:
                    if not get_feed(db_session, target_id):
                        logging.warning('Redirect target feed not found for feed %s: %s', feed_stable_id, target_id)
                        continue
                    feed.redirectingids.append(Redirectingid(
                        target_id=get_feed(db_session, target_id).id,
                        redirect_comment='Deprecated historical feed from TransitFeeds'
                    ))
            except Exception as e:
                logger.error('Redirect target feed not found for feed %s: %s', feed_stable_id, str(e))
                raise e

            # Location (shared)
            logger.debug("[%s] Resolving location for %s (Country=%s, Subdivision=%s, Municipality=%s)",
                         feed_kind.upper(), feed_stable_id, row['Country'], row['Subdivision'], row['Municipality'])
            location = create_or_get_location(
                db_session,
                country=row['Country'],
                state_province=row['Subdivision'] if not pd.isna(row['Subdivision']) else None,
                city_name=row['Municipality'] if not pd.isna(row['Municipality']) else None,
            )
            if not getattr(feed, "locations", []) and location:
                feed.locations = [location]
                logger.debug("[%s] Assigned first location to %s", feed_kind.upper(), feed_stable_id)

            total_processed += 1
            total_created += int(is_new)
            total_updated += int(not is_new)

        if not dry_run:
            logger.info("[%s] Committing DB transaction for %d processed feeds", feed_kind.upper(), total_processed)
            db_session.commit()
        else:
            logger.info("[%s] Dry-run enabled; no DB commit performed", feed_kind.upper())

        logger.info("[%s] Done. processed=%d created=%d updated=%d",
                    feed_kind.upper(), total_processed, total_created, total_updated)

        return {
            'message': f"Processed {total_processed} {feed_kind.upper()} feeds from TransitFeeds.",
            'total_processed': total_processed,
            'total_created': total_created,
            'total_updated': total_updated,
        }
    except Exception as error:
        traceback.print_exc()
        logger.exception("Error processing %s feeds: %s", feed_kind.upper(), error)
        raise


def _process_transitfeeds_gtfs(db_session: Session, dry_run: bool) -> dict:
    logger.info("Starting GTFS feeds processing (dry_run=%s)", dry_run)
    return _process_feeds(
        db_session=db_session,
        csv_filename='gtfs_feeds.csv',
        model_cls=Gtfsfeed,
        feed_kind='gtfs',
        dry_run=dry_run,
        on_is_new=None,
    )


def _process_transitfeeds_gtfs_rt(db_session: Session, dry_run: bool) -> dict:
    logger.info("Starting GTFS-RT feeds processing (dry_run=%s)", dry_run)

    def _rt_on_is_new(session: Session, feed, row: pd.Series) -> None:
        entity_types = _safe_split(row.get('Entity Types'))
        logger.debug("[GTFS_RT] %s entity types: %s", row['Mobility Database Feed ID'], entity_types)
        if entity_types:
            feed.entity_types = [
                _get_or_create_entity_type(session, et) for et in entity_types
            ]
            logger.info("[GTFS_RT] Set %d entity types for %s", len(entity_types), row['Mobility Database Feed ID'])

    return _process_feeds(
        db_session=db_session,
        csv_filename='gtfs_rt_feeds.csv',
        model_cls=Gtfsrealtimefeed,
        feed_kind='gtfs_rt',
        dry_run=dry_run,
        on_is_new=_rt_on_is_new,
    )


def _add_historical_datasets(db_session: Session, dry_run: bool) -> int:
    csv_path = os.path.join(os.path.dirname(__file__), 'historical_datasets.csv')
    logger.info("Adding historical datasets from CSV: %s (dry_run=%s)", csv_path, dry_run)
    df = pd.read_csv(csv_path)
    logger.debug("Historical datasets CSV loaded: %d rows", len(df))
    total_added = 0

    grouped = df.groupby('Feed ID')
    logger.debug("Grouped historical datasets by Feed ID: %d groups", len(grouped))

    for group_key, grouped_df in grouped:
        feed_stable_id = grouped_df['Feed ID'].iloc[0]
        logger.debug("Processing historical datasets for feed_stable_id=%s (%d rows)", feed_stable_id, len(grouped_df))
        feed = get_feed(db_session, feed_stable_id, model=Gtfsfeed)
        if not feed:
            logger.warning("Feed with stable_id=%s not found; skipping historical datasets.", feed_stable_id)
            continue

        grouped_df = grouped_df.sort_values(by='Dataset ID', ascending=False).reset_index(drop=True)

        datasets: list[Gtfsdataset] = []
        latest_candidate_id: Optional[str] = None
        latest_already_set = feed.latest_dataset_id is not None

        for i, row in enumerate(grouped_df.iterrows()):
            idx, row = row
            tfs_dataset_id = row['Dataset ID']
            tfs_dataset_suffix = tfs_dataset_id.split('/')[-1]
            mdb_dataset_stable_id = f"{feed_stable_id}-{tfs_dataset_suffix}"

            existing_dataset = db_session.query(Gtfsdataset).filter(
                Gtfsdataset.stable_id == mdb_dataset_stable_id
            ).first()

            if existing_dataset:
                logger.info("Historical dataset %s already exists; skipping creation.", existing_dataset.stable_id)
                if (i == 0) and not latest_already_set and latest_candidate_id is None:
                    latest_candidate_id = existing_dataset.id
                continue

            download_date = pd.to_datetime(tfs_dataset_suffix.split('-')[0], format='%Y%m%d', errors='coerce')
            if pd.isna(download_date):
                logger.warning("Invalid date in Dataset ID %s; skipping.", tfs_dataset_id)
                continue

            service_date_range_start = pd.to_datetime(row['Service Date Range Start'], format='%Y%m%d', errors='coerce')
            service_date_range_end = pd.to_datetime(row['Service Date Range End'], format='%Y%m%d', errors='coerce')

            dataset_id = str(uuid.uuid4())
            ds = Gtfsdataset(
                id=dataset_id,
                stable_id=mdb_dataset_stable_id,
                hosted_url=f"https://openmobilitydata-data.s3.us-west-1.amazonaws.com/public/feeds/{tfs_dataset_id}/gtfs.zip",
                downloaded_at=download_date,
                service_date_range_start=service_date_range_start if not pd.isna(service_date_range_start) else None,
                service_date_range_end=service_date_range_end if not pd.isna(service_date_range_end) else None,
                feed_id=feed.id,
            )
            datasets.append(ds)
            logger.debug("Prepared new dataset %s (downloaded_at=%s) for feed %s",
                         ds.stable_id, ds.downloaded_at, feed_stable_id)

            if (i == 0) and not latest_already_set and latest_candidate_id is None:
                latest_candidate_id = dataset_id

        if datasets:
            db_session.add_all(datasets)
            logger.debug("Added %d new historical datasets for %s to the session.", len(datasets), feed_stable_id)
        else:
            logger.debug("No new datasets to add for %s.", feed_stable_id)

        db_session.flush()

        if not latest_already_set and latest_candidate_id:
            feed.latest_dataset_id = latest_candidate_id
            logger.info("Set latest_dataset_id for feed %s to %s", feed_stable_id, latest_candidate_id)
            db_session.flush()

        total_added += len(datasets)
        logger.info("Assigned %d historical datasets to feed %s (latest_dataset_id=%s)",
                    len(datasets), feed_stable_id, feed.latest_dataset_id)

        if not dry_run:
            db_session.commit()
            logger.debug("Committed historical datasets for %s", feed_stable_id)
        else:
            logger.debug("Dry-run: skipped commit for %s", feed_stable_id)

    logger.info("Finished adding historical datasets. total_added=%d", total_added)
    return total_added


@with_db_session
def _sync_transitfeeds(db_session: Session, dry_run: bool = True) -> dict:
    logger.info("Starting TransitFeeds sync (dry_run=%s)", dry_run)
    gtfs_feeds_processing_result = _process_transitfeeds_gtfs(db_session, dry_run=dry_run)
    gtfs_rt_processing_result = _process_transitfeeds_gtfs_rt(db_session, dry_run=dry_run)

    datasets_added = _add_historical_datasets(db_session, dry_run=dry_run)

    total_processed = (
        gtfs_feeds_processing_result['total_processed'] +
        gtfs_rt_processing_result['total_processed']
    )
    logger.info("TransitFeeds sync complete. total_processed=%d datasets_added=%d",
                total_processed, datasets_added)

    return {
        'message': (
            f"Sync TransitFeeds completed. "
            f"Total processed feeds: {total_processed}. "
            f"Datasets added: {datasets_added}."
        ),
        'total_processed': total_processed,
        'datasets_added': datasets_added,
        'details': {
            'gtfs_feeds': gtfs_feeds_processing_result,
            'gtfs_rt_feeds': gtfs_rt_processing_result,
        }
    }


def sync_transitfeeds_handler(payload: dict | None = None) -> dict:
    """
    Syncs GTFS datasets from TransitFeeds entry point.
    @param payload: The payload containing the task details:
        {
            "dry_run": bool,  # [optional] If True, do not execute the sync
        }
    @return: A message indicating the result of the operation with the total_processed datasets.
    """
    payload = payload or {}
    dry_run_raw = payload.get("dry_run", True)
    dry_run = bool(dry_run_raw) if isinstance(dry_run_raw, bool) else str(dry_run_raw).lower() == "true"
    logger.info("Parsed dry_run parameter: %s (raw=%s)", dry_run, dry_run_raw)
    try:
        result = _sync_transitfeeds(dry_run=dry_run)
    except Exception as e:
        logger.exception("Error during TransitFeeds sync: %s", e)
        return {
            'message': f"Error during TransitFeeds sync: {str(e)}",
            'total_processed': 0,
            'error': str(e),
        }
    logger.info("Sync result: %s", {
        k: v for k, v in result.items()
    })
    return result
