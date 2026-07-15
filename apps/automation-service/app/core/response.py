from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel
from .camel import CamelModel

T = TypeVar("T")


class ResultObject(CamelModel, Generic[T]):
    code: int = 200
    msg: str = "操作成功"
    data: Optional[T] = None

    @staticmethod
    def success(data: Any = None, message: str = "操作成功") -> "ResultObject":
        return ResultObject(code=200, msg=message, data=data)

    @staticmethod
    def failed(message: str = "操作失败", code: int = 500) -> "ResultObject":
        return ResultObject(code=code, msg=message, data=None)

    @staticmethod
    def validate_failed(message: str = "参数验证失败") -> "ResultObject":
        return ResultObject(code=400, msg=message, data=None)

    @staticmethod
    def unauthorized(data: Any = None) -> "ResultObject":
        return ResultObject(code=401, msg="暂未登录或token已经过期", data=data)

    @staticmethod
    def forbidden(data: Any = None) -> "ResultObject":
        return ResultObject(code=403, msg="没有相关权限", data=data)