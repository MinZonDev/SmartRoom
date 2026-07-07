"""Domain exceptions — service layer raise các lỗi này, main.py ánh xạ sang HTTP status.

Giữ business logic độc lập với HTTP: service không được import HTTPException.
"""


class DomainError(Exception):
    """Lỗi nghiệp vụ gốc."""


class NotFoundError(DomainError):
    """Không tìm thấy tài nguyên."""


class PermissionDeniedError(DomainError):
    """Người dùng không có quyền trên tài nguyên."""


class ConflictError(DomainError):
    """Vi phạm ràng buộc nghiệp vụ/unique (HTTP 409)."""


class BillingError(DomainError):
    """Lỗi thuộc luồng hóa đơn."""


class MissingMeterReadingError(BillingError):
    """Chưa nhập chỉ số công tơ cho kỳ chốt — không thể tính tiền dịch vụ per_unit."""


class AuthError(DomainError):
    """Lỗi thuộc luồng xác thực."""


class EmailAlreadyExistsError(AuthError):
    """Email đã được đăng ký."""


class InvalidCredentialsError(AuthError):
    """Sai email/mật khẩu hoặc tài khoản bị khóa."""


class OCRError(DomainError):
    """Lỗi thuộc luồng OCR."""


class InvalidImageError(OCRError):
    """File upload không phải ảnh hợp lệ."""


class NoReadingDetectedError(OCRError):
    """Không phát hiện được cụm chữ số nào giống chỉ số đồng hồ trên ảnh."""
