from typing import Optional
from ..core.camel import CamelModel


class LoginReqDTO(CamelModel):
    username: str
    password: str


class RegisterReqDTO(CamelModel):
    username: str
    password: str
    confirm_password: str


class LoginRespDTO(CamelModel):
    token: str
    username: str


class CheckUserExistsRespDTO(CamelModel):
    exists: bool


class ChangePasswordReqDTO(CamelModel):
    old_password: str
    new_password: str


class LoginDeviceDTO(CamelModel):
    id: Optional[int] = None
    device_name: Optional[str] = None
    browser_name: Optional[str] = None
    os_name: Optional[str] = None
    login_ip: Optional[str] = None
    last_active_time: Optional[str] = None
    status: Optional[int] = None


class KickLoginDeviceReqDTO(CamelModel):
    token_id: int