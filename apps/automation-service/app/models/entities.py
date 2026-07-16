from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, Boolean, ForeignKey, Float, DECIMAL, SmallInteger, JSON, Index, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


# ============================================================
# 与 MySQL 表定义（与 core-api 对齐，包含 tenant_id）
# ============================================================

class XianyuAccount(Base):
    __tablename__ = "xianyu_account"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    user_id = Column(BigInteger, nullable=True, comment="所属用户ID")
    platform = Column(String(50), nullable=True, default="xianyu", comment="平台: xianyu")
    external_uid = Column(String(200), nullable=True, comment="闲鱼external_uid")
    nickname = Column(String(200), nullable=True)
    avatar_url = Column(Text, nullable=True)
    province = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    account_level = Column(String(50), nullable=True)
    remark = Column(Text, nullable=True)
    status = Column(SmallInteger, default=1, comment="1正常 0禁用")
    # 鱼小铺标识字段（与 Java XianyuAccount.fishShopUser 对齐，数据库列名 fish_shop_user）
    # 由 Java 端从闲鱼接口 superShow 字段解析后写入。Python 端只读，用于发布时区分账号类型
    fish_shop_user = Column(SmallInteger, default=0, comment="1鱼小铺账号 0普通账号")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuAccountAuth(Base):
    __tablename__ = "xianyu_account_auth"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    encrypted_cookie = Column(Text, nullable=True, comment="加密Cookie")
    encrypted_token = Column(Text, nullable=True, comment="加密Token")
    login_username = Column(String(255), nullable=True)
    encrypted_login_password = Column(Text, nullable=True)
    show_browser = Column(Boolean, default=False)
    cookie_status = Column(SmallInteger, default=0, comment="1正常 0待校验/失效 2过期")
    ws_token = Column(Text, nullable=True)
    token_expire_time = Column(DateTime, nullable=True)
    last_login_status_code = Column(String(64), nullable=True)
    last_login_status_message = Column(String(255), nullable=True)
    last_login_check_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuAccountRuntime(Base):
    __tablename__ = "xianyu_account_runtime"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    online_status = Column(SmallInteger, default=0, comment="1在线 0离线")
    ws_status = Column(SmallInteger, default=0, comment="1在线 0离线")
    ws_latency_ms = Column(Integer, default=0)
    cookie_status = Column(SmallInteger, default=0, comment="1正常 0待校验/失效 2过期")
    last_login_status_code = Column(String(64), nullable=True)
    last_login_status_message = Column(String(255), nullable=True)
    last_login_check_time = Column(DateTime, nullable=True)
    last_login_time = Column(DateTime, nullable=True)
    last_heartbeat_time = Column(DateTime, nullable=True)
    last_online_time = Column(DateTime, nullable=True)
    last_sync_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuAccountMembership(Base):
    __tablename__ = "xianyu_account_membership"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    membership_level = Column(String(50), nullable=True, comment="会员等级")
    status = Column(SmallInteger, default=1, comment="1正常 0过期")
    expired_time = Column(DateTime, nullable=True, comment="会员过期时间")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuAccountHealthSnapshot(Base):
    __tablename__ = "xianyu_account_health_snapshot"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    health_score = Column(Integer, default=100)
    api_success_rate = Column(Float, default=1.0)
    avg_response_ms = Column(Integer, default=0)
    ws_latency_ms = Column(Integer, default=0)
    collected_time = Column(DateTime, nullable=True)
    created_time = Column(DateTime, default=func.now())


class XianyuGoods(Base):
    __tablename__ = "xianyu_goods"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=True)
    goods_id = Column(String(100), nullable=True, comment="兼容旧商品ID字段")
    external_goods_id = Column(String(100), nullable=True, comment="闲鱼商品ID")
    title = Column(String(500), nullable=True, comment="商品标题")
    price = Column(String(50), nullable=True, comment="价格")
    sold_price = Column(String(50), nullable=True, comment="售价")
    cover_pic = Column(Text, nullable=True, comment="封面图URL")
    image_url = Column(Text, nullable=True, comment="图片URL")
    image_urls = Column(JSON, nullable=True, comment="图片URL列表")
    stock = Column(Integer, default=0, comment="库存")
    quantity = Column(Integer, default=0, comment="库存数量")
    exposure_count = Column(Integer, default=0, comment="曝光次数")
    view_count = Column(Integer, default=0, comment="浏览次数")
    want_count = Column(Integer, default=0, comment="想要人数")
    detail_url = Column(Text, nullable=True, comment="详情页URL")
    detail_info = Column(Text, nullable=True, comment="详情描述文字")
    description = Column(Text, nullable=True, comment="描述")
    raw_payload = Column(JSON, nullable=True, comment="原始商品数据快照")
    category = Column(String(100), nullable=True, comment="分类")
    sort_order = Column(Integer, default=0, comment="排序序号")
    status = Column(SmallInteger, default=1, comment="1在售 0下架 2已售")
    deleted = Column(SmallInteger, default=0)
    auto_reply_enabled = Column(SmallInteger, nullable=True, default=None, comment="NULL继承账号全局 0强制关 1强制开")
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())




class XianyuGoodsSyncTask(Base):
    __tablename__ = "xianyu_goods_sync_task"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sync_id = Column(String(80), nullable=False, unique=True, comment="同步任务ID")
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    status = Column(String(30), nullable=False, default="queued", comment="queued/running/completed/failed")
    progress = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    off_shelf_count = Column(Integer, default=0)
    detail_synced_count = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0)
    error_message = Column(Text, nullable=True)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuTradeOrder(Base):
    __tablename__ = "xianyu_trade_order"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True)
    external_order_id = Column(String(200), nullable=True, comment="闲鱼订单ID")
    order_status = Column(SmallInteger, default=0, comment="0待付款 1已付款 2待发货 3已发货 4已完成 5已关闭")
    total_amount = Column(String(50), nullable=True)
    buyer_name = Column(String(200), nullable=True)
    buyer_id = Column(String(200), nullable=True)
    create_time = Column(DateTime, nullable=True)
    pay_time = Column(DateTime, nullable=True)
    ship_time = Column(DateTime, nullable=True)
    confirm_time = Column(DateTime, nullable=True)
    buyer_message = Column(Text, nullable=True)
    item_id = Column(String(100), nullable=True, comment="商品ID")
    is_bargain = Column(SmallInteger, default=0, comment="是否小刀")
    is_rated = Column(SmallInteger, default=0, comment="是否已评价")
    is_red_flower = Column(SmallInteger, default=0, comment="是否已求小红花")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuTradeOrderItem(Base):
    __tablename__ = "xianyu_trade_order_item"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, nullable=False)
    tenant_id = Column(BigInteger, nullable=False)
    goods_id = Column(BigInteger, nullable=True)
    goods_name = Column(String(300), nullable=True)
    goods_title = Column(String(500), nullable=True)
    goods_image = Column(Text, nullable=True)
    goods_price = Column(DECIMAL(12, 2), nullable=True)
    price_cent = Column(BigInteger, default=0)
    goods_count = Column(Integer, default=1)
    quantity = Column(Integer, default=1)
    subtotal_cent = Column(BigInteger, default=0)
    sku_id = Column(String(100), nullable=True)
    sku_name = Column(String(200), nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class DeliveryRule(Base):
    __tablename__ = "delivery_rule"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(BigInteger, nullable=True)
    tenant_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    rule_name = Column(String(200), nullable=True)
    goods_id = Column(BigInteger, nullable=True)
    delivery_mode = Column(String(50), default="kami")
    card_group_id = Column(BigInteger, nullable=True)
    delivery_content = Column(Text, nullable=True)
    trigger_on_pay = Column(SmallInteger, default=1)
    trigger_keyword = Column(String(200), nullable=True)
    max_delivery_per_day = Column(Integer, default=0)
    status = Column(SmallInteger, default=1)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class CardGroup(Base):
    __tablename__ = "card_group"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    group_name = Column(String(200), nullable=False)
    group_type = Column(String(50), default="kami")
    total_count = Column(Integer, default=0)
    used_count = Column(Integer, default=0)
    available_count = Column(Integer, default=0)
    remark = Column(Text, nullable=True)
    status = Column(SmallInteger, default=1)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class CardItem(Base):
    __tablename__ = "card_item"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, nullable=False)
    tenant_id = Column(BigInteger, nullable=False)
    card_key = Column(Text, nullable=False)
    card_value = Column(Text, nullable=True)
    extra_info = Column(Text, nullable=True)
    is_used = Column(SmallInteger, default=0)
    used_time = Column(DateTime, nullable=True)
    used_by_order_id = Column(BigInteger, nullable=True)
    used_by_user = Column(String(200), nullable=True)
    expire_time = Column(DateTime, nullable=True)
    remark = Column(Text, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class DeliveryRecord(Base):
    """发货记录实体，用于统计发货成功/失败/待处理"""
    __tablename__ = "delivery_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    account_id = Column(BigInteger, nullable=True, comment="关联xianyu_account.id")
    order_id = Column(BigInteger, nullable=True, comment="关联xianyu_trade_order.id")
    rule_id = Column(BigInteger, nullable=True, comment="关联delivery_rule.id")
    delivery_type = Column(String(50), nullable=True)
    content = Column(Text, nullable=True)
    delivery_status = Column(String(50), default="pending", comment="发货状态 pending/success/failed")
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class Notification(Base):
    """系统通知实体"""
    __tablename__ = "notification"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    user_id = Column(BigInteger, nullable=True, comment="所属用户ID")
    notification_type = Column(String(50), nullable=True, comment="通知类型")
    title = Column(String(300), nullable=True)
    content = Column(Text, nullable=True)
    reference_type = Column(String(100), nullable=True)
    reference_id = Column(BigInteger, nullable=True)
    is_read = Column(SmallInteger, default=0, comment="0未读 1已读")
    read_time = Column(DateTime, nullable=True)
    priority = Column(SmallInteger, default=0, comment="优先级")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuConversation(Base):
    __tablename__ = "xianyu_conversation"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True)
    seller_external_uid = Column(String(64), nullable=True, comment="闲鱼卖家真实UID/unb")
    external_buyer_id = Column(String(200), nullable=True)
    peer_external_uid = Column(String(64), nullable=True, comment="买家UID（稳定）")
    peer_key = Column(String(128), nullable=True, comment="对端唯一标识（用于去重合并会话）")
    buyer_name = Column(String(200), nullable=True)
    buyer_avatar = Column(Text, nullable=True)
    goods_title = Column(String(500), nullable=True)
    goods_id = Column(String(200), nullable=True)
    goods_cover_pic = Column(Text, nullable=True, comment="商品封面图URL")
    status = Column(SmallInteger, default=0, comment="0进行中 1已完成 2已关闭")
    last_message_time = Column(DateTime, nullable=True)
    last_message_content = Column(Text, nullable=True)
    unread_count = Column(Integer, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuMessage(Base):
    __tablename__ = "xianyu_message"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True)
    conversation_id = Column(BigInteger, nullable=True)
    session_id = Column(String(200), nullable=True, comment="会话session ID，用于关联xianyu_chat_message.s_id")
    from_user_id = Column(String(200), nullable=True)
    to_user_id = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    message_type = Column(String(50), default="text", comment="text/image/card")
    direction = Column(String(20), default="received", comment="sent/received")
    is_auto_reply = Column(SmallInteger, default=0, comment="0否 1是")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())


class XianyuChatMessage(Base):
    """闲鱼 WebSocket 实时聊天消息（去重存储，含完整原始消息体）"""
    __tablename__ = "xianyu_chat_message"
    __table_args__ = (
        Index("idx_chat_msg_lookup", "tenant_id", "account_id", "deleted", "s_id", "message_time"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    account_id = Column(BigInteger, nullable=False, comment="闲鱼账号ID")
    seller_external_uid = Column(String(64), nullable=True, comment="闲鱼卖家真实UID/unb")
    pnm_id = Column(String(200), nullable=True, comment="消息唯一ID（去重）")
    message_uid = Column(String(128), nullable=True, comment="稳定消息唯一ID（用于去重）")
    s_id = Column(String(200), nullable=True, comment="会话ID")
    content_type = Column(Integer, default=1, comment="消息类型:1文本 2图片 14砍价 25已拍下 26已付款 28已发货 32已读")
    msg_content = Column(Text, nullable=True, comment="消息文本内容")
    sender_user_id = Column(String(200), nullable=True, comment="发送者ID")
    receiver_user_id = Column(String(64), nullable=True, comment="接收者用户ID")
    sender_user_name = Column(String(200), nullable=True, comment="发送者昵称")
    peer_external_uid = Column(String(64), nullable=True, comment="买家UID")
    xy_goods_id = Column(String(200), nullable=True, comment="关联商品ID")
    message_time = Column(BigInteger, default=0, comment="消息时间戳(毫秒)")
    direction = Column(String(20), default="IN", comment="IN/OUT")
    parse_status = Column(String(16), default="ok", comment="解析状态 ok/partial/failed")
    reminder_content = Column(Text, nullable=True, comment="提醒内容")
    reminder_url = Column(String(500), nullable=True, comment="提醒链接")
    complete_msg = Column(JSON, nullable=True, comment="完整原始消息体")
    raw_payload = Column(JSON, nullable=True, comment="原始消息payload（用于调试和重新解析）")
    read_status = Column(SmallInteger, default=0, comment="0未读 1已读")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class AutoReplyRule(Base):
    __tablename__ = "auto_reply_rule"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True)
    rule_name = Column(String(200), nullable=True)
    match_type = Column(String(50), default="keyword", comment="keyword/ai/all")
    match_keywords = Column(Text, nullable=True)
    reply_content = Column(Text, nullable=True)
    reply_mode = Column(String(50), default="keyword", comment="keyword/ai")
    status = Column(SmallInteger, default=1, comment="1启用 0禁用")
    priority = Column(Integer, default=0)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class QuickReplyTemplate(Base):
    """快捷回复模板：人工点击即插入到输入框的常用语，与自动回复规则解耦"""
    __tablename__ = "quick_reply_template"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True, comment="NULL 表示全租户通用")
    title = Column(String(200), nullable=False, comment="模板标题")
    content = Column(Text, nullable=False, comment="模板内容")
    sort_order = Column(Integer, default=0, comment="排序，越小越靠前")
    status = Column(SmallInteger, default=1, comment="1启用 0禁用")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuOperationLog(Base):
    __tablename__ = "operation_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    operation_type = Column(String(100), nullable=True)
    operation_desc = Column(Text, nullable=True)
    target_type = Column(String(100), nullable=True)
    target_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_time = Column(DateTime, default=func.now())


# Auth models for user login (from existing system)
class SysUser(Base):
    __tablename__ = "sys_user"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=True)
    username = Column(String(80), nullable=False)
    password_hash = Column(String(200), nullable=False)
    nickname = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(120), nullable=True)
    status = Column(SmallInteger, default=1)
    security_version = Column(BigInteger, nullable=False, default=1)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class TenantStorageAsset(Base):
    """Durable tenant storage reservation and cleanup audit record."""
    __tablename__ = "tenant_storage_asset"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    storage_key = Column(String(512), nullable=False, unique=True)
    public_url = Column(String(700), nullable=False)
    media_type = Column(String(100), nullable=True)
    source_type = Column(String(50), nullable=False)
    visibility = Column(String(16), nullable=False, default="private")
    purpose = Column(String(64), nullable=False, default="user-media")
    owner_type = Column(String(32), nullable=True)
    owner_id = Column(BigInteger, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="reserved")
    request_id = Column(String(128), nullable=True)
    deletion_reason = Column(String(255), nullable=True)
    cleaned_by = Column(String(120), nullable=True)
    reviewed_by = Column(String(120), nullable=True)
    approved_by = Column(String(120), nullable=True)
    activated_time = Column(DateTime, nullable=True)
    published_time = Column(DateTime, nullable=True)
    deleted_time = Column(DateTime, nullable=True)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("idx_storage_asset_tenant_status", "tenant_id", "status"),
        Index("idx_storage_asset_created", "created_time"),
        Index("idx_storage_asset_status_created", "status", "created_time"),
        Index("idx_storage_asset_status_size", "status", "size_bytes"),
        Index("idx_storage_asset_visibility_status", "visibility", "status", "updated_time"),
        Index("idx_storage_asset_owner", "tenant_id", "owner_type", "owner_id", "status"),
        CheckConstraint(
            "visibility IN ('private', 'public')",
            name="chk_storage_asset_visibility",
        ),
    )


class TenantUploadRateEvent(Base):
    """Cross-process upload admission event used for tenant rate limiting."""
    __tablename__ = "tenant_upload_rate_event"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    request_id = Column(String(128), nullable=True)
    created_time = Column(DateTime, default=func.now())
    __table_args__ = (
        Index("idx_upload_rate_tenant_time", "tenant_id", "created_time"),
        Index("idx_upload_rate_created", "created_time"),
    )


class SysLoginToken(Base):
    __tablename__ = "sys_login_token"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    tenant_id = Column(BigInteger, nullable=True)
    token = Column(String(500), nullable=False)
    device_id = Column(String(100), nullable=True)
    device_name = Column(String(200), nullable=True)
    browser_name = Column(String(100), nullable=True)
    os_name = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    login_ip = Column(String(50), nullable=True)
    expire_time = Column(DateTime, nullable=False)
    last_active_time = Column(DateTime, nullable=True)
    status = Column(SmallInteger, default=1)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================
# 后台动态配置模块
# 说明：Phase7 起不再让 automation-service 自动创建旧业务兼容表。
# 旧业务数据需通过 DB_MIGRATION_PHASE7.sql 迁移到规范表后归档。
# ============================================================

class XianyuSysSetting(Base):
    __tablename__ = "xianyu_sys_setting"
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), nullable=True)
    setting_value = Column(Text, nullable=True)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuAiProvider(Base):
    __tablename__ = "xianyu_ai_provider"
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String(100), nullable=True)
    api_key = Column(String(500), nullable=True)
    base_url = Column(String(500), nullable=True)
    model_name = Column(String(200), nullable=True)
    status = Column(Integer, default=1)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================
# 工作流相关表
# ============================================================

class WorkflowDefinition(Base):
    """工作流定义"""
    __tablename__ = "workflow_definition"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    user_id = Column(BigInteger, nullable=True, comment="创建者用户ID")
    name = Column(String(200), nullable=False, comment="工作流名称")
    description = Column(Text, nullable=True, comment="描述说明")
    trigger_type = Column(String(50), default="manual", comment="触发方式: manual/scheduled/event")
    config_json = Column(JSON, nullable=True, comment="全局配置JSON")
    canvas_json = Column(JSON, nullable=True, comment="画布配置(zoom缩放)")
    status = Column(String(30), default="draft", comment="draft/published/disabled")
    version = Column(Integer, default=1, comment="版本号")
    execution_count = Column(Integer, default=0, comment="执行次数")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowNode(Base):
    """工作流节点"""
    __tablename__ = "workflow_node"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    workflow_id = Column(BigInteger, nullable=False, comment="关联工作流ID")
    node_key = Column(String(80), nullable=False, comment="节点唯一标识")
    node_name = Column(String(200), nullable=True, comment="节点名称")
    node_type = Column(String(50), nullable=False, comment="节点类型")
    position_x = Column(Integer, default=80)
    position_y = Column(Integer, default=80)
    config_json = Column(JSON, nullable=True, comment="节点配置参数")
    retry_enabled = Column(SmallInteger, default=0)
    retry_count = Column(Integer, default=0)
    retry_interval_seconds = Column(Integer, default=30)
    sort_order = Column(Integer, default=0, comment="排序序号")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowEdge(Base):
    """工作流节点连接"""
    __tablename__ = "workflow_edge"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    workflow_id = Column(BigInteger, nullable=False)
    source_node_key = Column(String(80), nullable=False)
    target_node_key = Column(String(80), nullable=False)
    condition_expr = Column(String(500), nullable=True, comment="流转条件表达式")
    sort_order = Column(Integer, default=0)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())


class WorkflowExecution(Base):
    """工作流执行记录"""
    __tablename__ = "workflow_execution"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    workflow_id = Column(BigInteger, nullable=False)
    workflow_name = Column(String(200), nullable=True)
    execution_no = Column(String(80), nullable=False, unique=True, comment="执行编号")
    trigger_mode = Column(String(30), default="manual", comment="manual/test/scheduled")
    status = Column(String(30), default="queued", comment="queued/running/success/failed/terminated")
    current_node_key = Column(String(80), nullable=True, comment="当前执行节点")
    progress = Column(Integer, default=0, comment="进度百分比")
    node_total = Column(Integer, default=0)
    node_success = Column(Integer, default=0)
    node_failed = Column(Integer, default=0)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, default=0)
    is_test = Column(SmallInteger, default=0, comment="1=测试模式 0=正式")
    error_message = Column(Text, nullable=True)
    output_json = Column(JSON, nullable=True, comment="执行输出结果")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowNodeLog(Base):
    """工作流节点执行日志"""
    __tablename__ = "workflow_node_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=False)
    workflow_id = Column(BigInteger, nullable=True)
    node_key = Column(String(80), nullable=False)
    node_name = Column(String(200), nullable=True)
    node_type = Column(String(50), nullable=True)
    status = Column(String(30), default="pending", comment="pending/running/success/skipped/failed/retrying")
    input_json = Column(JSON, nullable=True, comment="节点输入参数")
    output_json = Column(JSON, nullable=True, comment="节点输出结果")
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    is_skipped = Column(SmallInteger, default=0)
    ai_request_summary = Column(Text, nullable=True, comment="AI请求摘要")
    ai_response_summary = Column(Text, nullable=True, comment="AI响应摘要")
    publish_params_summary = Column(Text, nullable=True, comment="发布参数摘要")
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowTimeline(Base):
    """工作流执行时间线"""
    __tablename__ = "workflow_timeline"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=True)
    workflow_id = Column(BigInteger, nullable=True)
    node_key = Column(String(80), nullable=True)
    event_level = Column(String(20), default="INFO", comment="INFO/WARN/ERROR/DEBUG")
    event_type = Column(String(50), nullable=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())


class WorkflowArtifact(Base):
    """工作流执行产物"""
    __tablename__ = "workflow_artifact"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=True)
    node_key = Column(String(80), nullable=True)
    artifact_type = Column(String(50), nullable=True, comment="goods/text/image/publish_plan")
    title = Column(String(500), nullable=True)
    content_json = Column(JSON, nullable=True)
    file_url = Column(String(1000), nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())


class WorkflowStateVariable(Base):
    """工作流状态变量"""
    __tablename__ = "workflow_state_variable"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=True)
    node_key = Column(String(80), nullable=True)
    var_name = Column(String(200), nullable=False)
    var_value = Column(Text, nullable=True)
    var_type = Column(String(30), default="string")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowCheckpoint(Base):
    """工作流检查点"""
    __tablename__ = "workflow_checkpoint"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=True)
    workflow_id = Column(BigInteger, nullable=True)
    node_key = Column(String(80), nullable=True)
    checkpoint_type = Column(String(30), default="snapshot")
    state_snapshot = Column(JSON, nullable=True)
    context_json = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    status = Column(String(30), default="active", comment="active/history")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class WorkflowPublishRecord(Base):
    """工作流发布记录"""
    __tablename__ = "workflow_publish_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    execution_id = Column(BigInteger, nullable=False)
    workflow_id = Column(BigInteger, nullable=True)
    account_id = Column(BigInteger, nullable=True, comment="发布账号ID")
    goods_id = Column(String(100), nullable=True, comment="发布成功后的商品ID")
    xianyu_goods_id = Column(String(100), nullable=True, comment="闲鱼商品ID")
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    price = Column(String(50), nullable=True)
    stock = Column(Integer, default=999, comment="固定库存999")
    image_urls = Column(JSON, nullable=True, comment="图片URL列表")
    address_info = Column(JSON, nullable=True, comment="地址信息")
    publish_time = Column(DateTime, nullable=True)
    status = Column(String(30), default="pending", comment="pending/success/failed")
    error_message = Column(Text, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuCaptchaSolveRecord(Base):
    """滑块求解记录"""
    __tablename__ = "xianyu_captcha_solve_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    account_id = Column(BigInteger, nullable=False, comment="账号ID")
    account_name = Column(String(128), default="", comment="账号名称")
    event_desc = Column(String(255), nullable=False, comment="事件描述")
    open_reason = Column(String(255), default="", comment="开启原因：为什么打开滑块求解流程（手动/自动 等）")
    solve_reason = Column(String(255), default="", comment="求解原因：为什么进行滑块求解（具体业务原因）")
    trigger_scene = Column(String(64), default="", comment="触发场景: ws_connect/cookie_keepalive/token_refresh/manual")
    result = Column(String(32), default="", comment="处理结果: slider_success/slider_fail")
    status = Column(String(32), nullable=False, default="retrying", comment="处理状态: retrying/success/fail")
    engine = Column(String(64), default="Playwright", comment="验证引擎")
    retry_count = Column(Integer, default=0, comment="重试次数")
    error_message = Column(Text, nullable=True, comment="错误详情")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted = Column(SmallInteger, default=0)

