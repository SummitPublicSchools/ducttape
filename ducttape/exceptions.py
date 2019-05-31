# -*- coding: utf-8 -*-
# exceptions.py - custom exceptions used throughout the package

"""
ducttape.exceptions
~~~~~~~~~~~~~~~~~~
Exceptions used in ducttape.
"""


class DuctTapeException(Exception):
    """A base class for ducttape's exceptions."""


class RequestError(DuctTapeException):
    """Error while sending API request."""


class IncorrectCellLabel(DuctTapeException):
    """The cell label is incorrect."""


class WorksheetNotFound(DuctTapeException):
    """Trying to open non-existent or inaccessible worksheet."""


class InvalidDimension(DuctTapeException):
    """Dimension passed is not ROWS or COLUMNS."""


class ReportNotReady(DuctTapeException):
    """Trying to download report that is still generating."""


class ReportNotFound(DuctTapeException):
    """A specified report could not be found."""


class NoDataError(DuctTapeException):
    """No data present in downloaded report."""


class InvalidLoginCredentials(DuctTapeException):
    """The username or password for logging in is incorrect."""


class InvalidIMAPParameters(DuctTapeException):
    """Check the credentials and the email folder for the email account."""
