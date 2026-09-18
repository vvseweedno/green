class MRVError(Exception):
    """Base domain error."""


class ValidationError(MRVError):
    """Invalid request or configuration."""


class DataUnavailableError(MRVError):
    """Required data is not available for a requested calculation."""


class CoverageError(MRVError):
    """Coverage is insufficient for a calculation that requires full coverage."""
