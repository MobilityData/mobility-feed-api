from packaging.version import Version


def compare_java_versions(v1: str | None, v2: str | None):
    """
    Compare two version strings v1 and v2.
    Returns 1 if v1 > v2, -1 if v1 < v2,
    otherwise 0.
    The version strings are expected to be in the format of
    major.minor.patch[-SNAPSHOT]
    """
    if v1 is None and v2 is None:
        return 0
    if v1 is None:
        return -1
    if v2 is None:
        return 1
    # clean version strings replacing the SNAPSHOT suffix with .dev0
    v1 = v1.replace("-SNAPSHOT", ".dev0")
    v2 = v2.replace("-SNAPSHOT", ".dev0")
    if Version(v1) > Version(v2):
        return 1
    elif Version(v1) < Version(v2):
        return -1
    else:
        return 0
