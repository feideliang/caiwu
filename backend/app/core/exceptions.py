"""Custom exception classes mapped to unified error codes."""

from __future__ import annotations

from app.core.response import ErrorCode


class AppException(Exception):
    """Base application exception carrying an error code and message."""

    code: int = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(self, message: str, code: int | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class ValidationError(AppException):
    code = ErrorCode.VALIDATION_ERROR
    status_code = 400


class MissingFieldError(ValidationError):
    code = ErrorCode.MISSING_FIELD


class InvalidFormatError(ValidationError):
    code = ErrorCode.INVALID_FORMAT


class AuthenticationError(AppException):
    code = ErrorCode.UNAUTHENTICATED
    status_code = 401


class ForbiddenError(AppException):
    code = ErrorCode.FORBIDDEN
    status_code = 403


class ResourceNotFoundError(AppException):
    code = ErrorCode.NOT_FOUND
    status_code = 404


class ConflictError(AppException):
    code = ErrorCode.CONFLICT
    status_code = 409


class AlreadyExistsError(ConflictError):
    code = ErrorCode.ALREADY_EXISTS


class BusinessError(AppException):
    code = ErrorCode.BUSINESS_ERROR
    status_code = 400


class DataQualityCheckFailedError(BusinessError):
    code = ErrorCode.DATA_QUALITY_CHECK_FAILED


class SyncFailedError(BusinessError):
    code = ErrorCode.SYNC_FAILED


class ReportGenerationFailedError(BusinessError):
    code = ErrorCode.REPORT_GENERATION_FAILED


class DatabaseError(AppException):
    code = ErrorCode.DATABASE_ERROR
    status_code = 500


class ExternalServiceError(AppException):
    code = ErrorCode.EXTERNAL_SERVICE_ERROR
    status_code = 502


class AppTimeoutError(AppException):
    code = ErrorCode.TIMEOUT_ERROR
    status_code = 504
