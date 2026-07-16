from typing import Optional, List, Any
from ..core.camel import CamelModel


class OrderQueryReqDTO(CamelModel):
    xianyu_account_id: Optional[int] = None
    xy_goods_id: Optional[str] = None
    order_status: Optional[int] = None
    page_num: Optional[int] = 1
    page_size: Optional[int] = 20


class ConfirmShipmentReqDTO(CamelModel):
    xianyu_account_id: int
    order_id: str
    is_bargain: Optional[bool] = False
    item_id: Optional[str] = None
    buyer_id: Optional[str] = None


class SoldOrderSyncReqDTO(CamelModel):
    xianyu_account_id: int


class OrderVO(CamelModel):
    """适配新 XianyuTradeOrder 实体的 DTO"""
    id: Optional[int] = None
    # 新实体字段
    account_id: Optional[int] = None          # 原 xianyu_account_id
    external_order_id: Optional[str] = None   # 原 order_id
    order_status: Optional[int] = None
    buyer_name: Optional[str] = None
    total_amount: Optional[str] = None        # 原 total_price
    create_time: Optional[str] = None
    pay_time: Optional[str] = None
    # 向后兼容字段
    xianyu_account_id: Optional[int] = None
    xy_goods_id: Optional[str] = None
    order_id: Optional[str] = None
    goods_title: Optional[str] = None
    goods_price: Optional[str] = None
    goods_count: Optional[int] = None
    total_price: Optional[str] = None


class OrderListData(CamelModel):
    records: List[OrderVO] = []
    total: int = 0
    page_num: int = 1
    page_size: int = 20
    pages: int = 0