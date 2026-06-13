"""
自定义异常类
"""


class API2MCPException(Exception):
    """API2MCP 基础异常类"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ResourceNotFoundError(API2MCPException):
    """资源不存在"""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code=404
        )


class ResourceExistsError(API2MCPException):
    """资源已存在"""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            code=409
        )


class ValidationError(API2MCPException):
    """数据验证错误"""

    def __init__(self, message: str):
        super().__init__(message=message, code=400)


class AuthenticationError(API2MCPException):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code=401)


class AuthorizationError(API2MCPException):
    """授权错误"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, code=403)


class ExternalServiceError(API2MCPException):
    """外部服务调用错误"""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"External service error ({service}): {message}",
            code=502
        )
