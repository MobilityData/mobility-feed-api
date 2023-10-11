from enum import Enum


class Status(Enum):
    UPDATED = 0
    NOT_UPDATED = 1
    FAILED = 2
    DO_NOT_RETRY = 3
    PUBLISHED = 4