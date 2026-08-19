from typing import Dict, Optional

from extractors.base import FileDataExtractor
from extractors.feed_info_extractor import FeedInfoExtractor

# Registry of GTFS file name -> extractor. Add new extractors here; the producer
# side (batch_process_dataset/pipeline_tasks.py EXTRACTABLE_FILES) decides which
# files actually get enqueued.
EXTRACTORS: Dict[str, FileDataExtractor] = {
    extractor.file_name: extractor for extractor in (FeedInfoExtractor(),)
}


def get_extractor(file_name: str) -> Optional[FileDataExtractor]:
    """Return the extractor registered for ``file_name``, or None if unsupported."""
    return EXTRACTORS.get(file_name)
