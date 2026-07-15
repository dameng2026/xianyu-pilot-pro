from typing import Optional, List
from ..core.camel import CamelModel


class AccountReqDTO(CamelModel):
    account_note: Optional[str] = None
    unb: Optional[str] = None
    cookie: Optional[str] = None


class ManualAddAccountReqDTO(CamelModel):
    account_note: Optional[str] = None
    cookie: str


class UpdateAccountReqDTO(CamelModel):
    account_id: int
    account_note: Optional[str] = None
    update_proxy: Optional[bool] = None
    proxy_type: Optional[str] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    clear_login_password: Optional[bool] = None


class UpdateCookieReqDTO(CamelModel):
    account_id: int
    cookie: str


class DeleteAccountReqDTO(CamelModel):
    account_id: int


class GetAccountDetailReqDTO(CamelModel):
    account_id: int


class RefreshAccountProfileReqDTO(CamelModel):
    account_id: int


class AccountProfileDTO(CamelModel):
    """适配新 XianyuAccount 实体的 DTO"""
    id: Optional[int] = None
    # 新实体字段
    external_uid: Optional[str] = None       # 原 unb
    nickname: Optional[str] = None            # 原 display_name
    avatar_url: Optional[str] = None          # 原 avatar
    remark: Optional[str] = None              # 原 account_note
    province: Optional[str] = None
    city: Optional[str] = None
    ip_location: Optional[str] = None         # province + city 拼接
    account_level: Optional[str] = None
    status: Optional[int] = None
    created_time: Optional[str] = None
    # 向后兼容字段（前端可能仍在使用）
    unb: Optional[str] = None
    account_note: Optional[str] = None
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    # 旧字段保留但置空
    proxy_type: Optional[str] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    login_username: Optional[str] = None
    login_password: Optional[str] = None


class GetAccountListRespDTO(CamelModel):
    accounts: List[AccountProfileDTO] = []


class AddAccountRespDTO(CamelModel):
    account_id: Optional[int] = None
    message: str = "添加成功"


class UpdateAccountRespDTO(CamelModel):
    message: str = "更新成功"


class UpdateCookieRespDTO(CamelModel):
    message: str = "更新成功"


class DeleteAccountRespDTO(CamelModel):
    message: str = "删除成功"


class GetAccountDetailRespDTO(CamelModel):
    account: Optional[AccountProfileDTO] = None


class RefreshAccountProfileRespDTO(CamelModel):
    account: Optional[AccountProfileDTO] = None
    message: str = "刷新成功"


class LoginCredentialRespDTO(CamelModel):
    account_id: Optional[int] = None
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    has_login_password: Optional[bool] = None
    show_browser: Optional[bool] = None
