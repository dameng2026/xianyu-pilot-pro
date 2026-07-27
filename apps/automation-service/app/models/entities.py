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
    exposure_count_30d = Column(Integer, default=0, comment="最近30天曝光次数（鱼小铺数据罗盘 showPv）")
    view_count_30d = Column(Integer, default=0, comment="最近30天浏览次数（鱼小铺数据罗盘 ipv）")
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
    # 闲鱼商品创建时间（鱼小铺商品管理接口 gmtCreate 字段，与本地 created_time 区分）
    gmt_create = Column(DateTime, nullable=True, comment="闲鱼商品创建时间")
    # 鱼小铺商品编辑能力（来自商品管理列表 itemExtendList.itemEdit / itemOperationInfo）
    # 1=可编辑（默认），0=不可编辑。前端"编辑"按钮据此判断是否允许进入编辑页。
    can_edit = Column(SmallInteger, nullable=False, default=1, comment="鱼小铺商品是否支持编辑：1=可编辑，0=不可编辑")
    # 不可编辑时的提示文案（来自 itemExtendList.itemEdit.note）
    edit_note = Column(String(500), nullable=False, default="", comment="鱼小铺商品不可编辑时的提示文案")
    # 售整自动上架相关字段（V1.38 / V1.20）
    # 开关：0关 1开。开启后当库存为1且被卖出时自动重发。
    auto_relist_enabled = Column(SmallInteger, nullable=False, default=0, comment="售整自动上架开关：0关 1开")
    # 重发后的新商品记录ID（用于追溯重发链路）
    next_relist_goods_id = Column(BigInteger, nullable=True, comment="重发后的新商品记录ID")
    # 本商品是从哪个原商品重发来的（用于防止无限链式重发）
    relist_source_goods_id = Column(BigInteger, nullable=True, comment="本商品是从哪个原商品重发来的")
    # 上次重发时间（用于限流与诊断）
    last_relist_at = Column(DateTime, nullable=True, comment="上次重发时间")
    # 是否有完整数据快照（冗余字段，避免跨库查询 xianyu_goods_edit_snapshot）
    has_snapshot = Column(SmallInteger, nullable=False, default=0, comment="是否有完整数据快照：0无 1有")
    # 商品原始库存（用于判定是否为"售整"场景：original_quantity==1）
    original_quantity = Column(Integer, nullable=True, comment="商品原始库存")
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
    # remain_count 与 available_count 语义相同（均 = status=0 的未使用卡密数），
    # 但 Java 端 CardGroupMapper.refreshCounts 和前端（卡密仓库/货源库页面）读取的是 remain_count，
    # 因此 Python 端必须同时维护两个字段，否则前端显示的"可用/库存"数量会停留在旧值。
    remain_count = Column(Integer, default=0)
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
    auto_reply_paused = Column(SmallInteger, default=0, comment="会话级自动回复是否暂停 0否 1是（人工干预或手动关闭触发）")
    auto_reply_manual_disabled = Column(SmallInteger, default=0, comment="是否被用户手动关闭 0否 1是（1时不允许自动恢复，仅手动开启）")
    last_manual_reply_at = Column(BigInteger, nullable=True, comment="最后一次人工回复时间戳（毫秒），用于1分钟自动恢复判断")
    last_auto_reply_at = Column(BigInteger, nullable=True, comment="最后一次 AI 自动回复时间戳（毫秒）")
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
    is_auto_reply = Column(SmallInteger, default=0, comment="是否 AI 自动回复 0否 1是")
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


class WorkflowGoodsDraft(Base):
    """工作流商品草稿箱：发布前先存草稿，无论成功失败都保留

    与 workflow_publish_record（发布动作日志）的区别：
    - workflow_publish_record：每次发布动作都新增一条记录（动作流水）
    - workflow_goods_draft：每个商品对应一条草稿记录，可重复发布（状态机）
    """
    __tablename__ = "workflow_goods_draft"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=True)
    workflow_id = Column(BigInteger, nullable=True, index=True)
    workflow_execution_id = Column(BigInteger, nullable=True, index=True)
    workflow_name = Column(String(200), nullable=True, comment="工作流名称（冗余存储）")
    node_key = Column(String(100), nullable=True, comment="产生该商品的节点key")
    account_id = Column(BigInteger, nullable=True, comment="闲鱼账号ID")
    title = Column(String(500), nullable=False)
    price = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    cover_pic = Column(Text, nullable=True, comment="封面图URL")
    image_urls = Column(JSON, nullable=True, comment="图片URL列表")
    category = Column(String(100), nullable=True)
    stock = Column(Integer, default=1)
    location = Column(JSON, nullable=True, comment="发货地")
    raw_payload = Column(JSON, nullable=True, comment="原始商品数据快照")
    source_item_id = Column(String(100), nullable=True, comment="源商品ID（去重用）")
    source_title_hash = Column(String(64), nullable=True, comment="源标题hash（去重用）")
    publish_status = Column(String(20), default="draft", nullable=False, index=True,
                            comment="draft/publishing/published/failed")
    publish_time = Column(DateTime, nullable=True)
    xianyu_goods_id = Column(String(100), nullable=True)
    publish_error_message = Column(Text, nullable=True)
    publish_attempt_count = Column(Integer, default=0)
    created_time = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted = Column(SmallInteger, default=0, nullable=False)


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
    # V1.15 新增字段：优先级调度 + 失败原因分类 + 队列时间追踪
    priority = Column(SmallInteger, nullable=False, default=0, comment="优先级: 0=普通 1=VIP 2=SVIP")
    failure_reason = Column(String(64), nullable=False, default="", comment="失败原因分类")
    queued_at = Column(DateTime, nullable=True, comment="入队时间")
    started_at = Column(DateTime, nullable=True, comment="开始处理时间")
    finished_at = Column(DateTime, nullable=True, comment="完成处理时间")


class ApiCaptchaSolveRecord(Base):
    """API 对接滑块求解记录（与内部 xianyu_captcha_solve_record 物理隔离）"""
    __tablename__ = "xianyu_api_captcha_solve_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="调用方租户")
    api_key_prefix = Column(String(8), nullable=False, comment="调用方密钥前 8 位")
    client_ip = Column(String(45), nullable=True, comment="调用方 IP")
    request_id = Column(String(32), nullable=False, unique=True, comment="请求唯一 ID")
    event_desc = Column(String(255), nullable=True, comment="事件描述")
    trigger_scene = Column(String(64), nullable=False, default="api", comment="触发场景，固定 api")
    result = Column(String(32), nullable=True, comment="处理结果")
    status = Column(String(32), nullable=False, default="queued",
                    comment="queued/retrying/success/fail/timeout/precheck_rejected/stale_terminated")
    engine = Column(String(64), nullable=False, default="Playwright")
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True, comment="错误详情（cookie 已脱敏）")
    priority = Column(Integer, nullable=False, default=0)
    failure_reason = Column(String(64), nullable=False, default="", comment="失败原因分类")
    queued_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    open_reason = Column(String(255), nullable=True)
    solve_reason = Column(String(255), nullable=True)
    token_charged = Column(Integer, nullable=False, default=0, comment="实际扣费 Token 数")
    token_charge_failed = Column(SmallInteger, nullable=False, default=0, comment="1=扣费失败需对账")
    duration_ms = Column(Integer, nullable=True, comment="求解耗时毫秒")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    deleted = Column(SmallInteger, nullable=False, default=0)


# ============================================================
# 鱼小铺多规格商品 SKU / 规格 / 规格图片 / 编辑快照
# 对应 V1.19 迁移脚本，仅鱼小铺账号发布/编辑多规格商品时使用
# ============================================================

class XianyuGoodsProperty(Base):
    """鱼小铺商品规格类型（颜色、尺码等）。一个商品最多 2 个规格类型。"""
    __tablename__ = "xianyu_goods_property"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False, comment="租户ID")
    account_id = Column(BigInteger, nullable=False, comment="闲鱼账号ID")
    external_goods_id = Column(String(128), nullable=False, comment="闲鱼商品itemId")
    property_name = Column(String(128), nullable=False, comment="规格名称")
    support_image = Column(SmallInteger, nullable=False, default=0, comment="是否支持规格图片：1是 0否")
    sort_order = Column(Integer, nullable=False, default=0)
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuGoodsPropertyValue(Base):
    """鱼小铺商品规格值（红色、蓝色、S、M、L 等）。"""
    __tablename__ = "xianyu_goods_property_value"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    property_id = Column(BigInteger, nullable=False, comment="关联规格类型ID")
    external_goods_id = Column(String(128), nullable=False)
    property_value = Column(String(255), nullable=False, comment="规格值")
    property_value_img = Column(String(512), nullable=True, comment="规格图片URL（仅 support_image=1 时有值）")
    sort_order = Column(Integer, nullable=False, default=0)
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuGoodsSku(Base):
    """鱼小铺商品 SKU（每个规格组合一行）。property_key 用于响应乱序匹配。"""
    __tablename__ = "xianyu_goods_sku"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    external_goods_id = Column(String(128), nullable=False, comment="闲鱼商品itemId")
    sku_id = Column(String(128), nullable=True, comment="闲鱼返回的skuId")
    inventory_id = Column(String(128), nullable=True, comment="闲鱼返回的inventoryId")
    property_list_json = Column(JSON, nullable=False, comment="规格组合：[{propertyText,valueText}, ...]")
    property_key = Column(String(512), nullable=False, comment="规格组合规范化键")
    price_in_cent = Column(BigInteger, nullable=False, default=0, comment="SKU价格（单位：分）")
    quantity = Column(Integer, nullable=False, default=0, comment="SKU库存")
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuGoodsEditSnapshot(Base):
    """鱼小铺/普通账号商品编辑快照，保存发布/编辑成功后的完整商品数据，用于后续编辑回显兜底与售整自动上架。"""
    __tablename__ = "xianyu_goods_edit_snapshot"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    external_goods_id = Column(String(128), nullable=False)
    snapshot_json = Column(JSON, nullable=False, comment="完整商品数据快照")
    source = Column(String(32), nullable=False, default="publish", comment="快照来源：publish/edit/detail_api/relist")
    account_type = Column(String(16), nullable=False, default="fish_shop", comment="账号类型：fish_shop / normal")
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRefund(Base):
    """闲鱼退款记录（多账号聚合）。按 (tenant_id, account_id, external_refund_id) 唯一。"""
    __tablename__ = "xianyu_refund"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    external_refund_id = Column(String(64), nullable=False, comment="闲鱼退款ID（字符串存储避免大整数精度丢失）")
    external_order_id = Column(String(64), nullable=True)
    external_item_id = Column(String(64), nullable=True)
    item_title = Column(String(500), nullable=True)
    item_pic_url = Column(Text, nullable=True)
    item_info_lines = Column(Text, nullable=True)
    buy_num = Column(String(32), nullable=True, comment="购买件数（保留原始字符串）")
    refund_fee = Column(DECIMAL(18, 4), nullable=True, comment="退款金额（十进制存储避免浮点误差）")
    auction_price = Column(DECIMAL(18, 4), nullable=True)
    order_status = Column(String(64), nullable=True, comment="退款大类（未发货退款/已发货退款/退货退款）")
    order_simple_remark = Column(String(255), nullable=True)
    refund_status = Column(String(64), nullable=True)
    refund_status_desc = Column(String(500), nullable=True)
    common_refund_status = Column(String(64), nullable=True)
    refund_reason = Column(String(500), nullable=True)
    cs_status = Column(String(64), nullable=True)
    logistics_company = Column(String(128), nullable=True)
    logistics_mail_no = Column(String(128), nullable=True)
    consign_time = Column(DateTime, nullable=True)
    refund_create_time = Column(DateTime, nullable=True, comment="退款申请时间（refundInfoVO.gmtCreate）")
    common_create_time = Column(DateTime, nullable=True, comment="订单创建时间回退字段")
    buyer_nick = Column(String(255), nullable=True, comment="买家昵称（脱敏存储）")
    right_buttons_json = Column(Text, nullable=True, comment="操作按钮列表 JSON（rightVO.btnList）")
    ext_total_refund_fee = Column(DECIMAL(18, 4), nullable=True)
    raw_json = Column(Text, nullable=True, comment="原始响应记录（脱敏后）")
    sync_status = Column(String(32), nullable=False, default="synced", comment="synced/pending_refresh")
    last_synced_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, nullable=False, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRefundSyncTask(Base):
    """退款同步任务追踪（参考 XianyuGoodsSyncTask 模式）。"""
    __tablename__ = "xianyu_refund_sync_task"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sync_id = Column(String(80), nullable=False, unique=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True, comment="NULL 表示全部账号聚合任务")
    scope = Column(String(20), nullable=False, default="single", comment="single / all")
    status = Column(String(30), nullable=False, default="queued", comment="queued/running/completed/failed")
    progress = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    new_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    succeeded_count = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRefundAccountState(Base):
    """账号级退款同步状态：记录最后同步时间、缓存过期判断、任务去重。"""
    __tablename__ = "xianyu_refund_account_state"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    last_sync_time = Column(DateTime, nullable=True)
    last_sync_status = Column(String(30), nullable=True, comment="success/failed/partial")
    last_sync_error = Column(String(500), nullable=True)
    last_total_count = Column(Integer, nullable=True)
    is_syncing = Column(SmallInteger, nullable=False, default=0, comment="1=同步中（任务去重）")
    sync_started_time = Column(DateTime, nullable=True)
    last_full_sync_time = Column(DateTime, nullable=True, comment="最后一次完整同步时间")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRate(Base):
    """闲鱼评价记录（多账号聚合）。按 (tenant_id, account_id, external_order_id) 唯一。

    评价按订单维度存储：一个订单只允许一次卖家评价（has_seller_rate 标识是否已评价）。
    seller_rate_status 仅存储原始字符串，不作语义判定（项目无确认映射）；
    评价可否由 has_seller_rate（rateItemVOList 中是否存在 seller=true 记录）综合判断。
    """
    __tablename__ = "xianyu_rate"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    external_order_id = Column(String(64), nullable=False, comment="订单ID（字符串存储避免大整数精度丢失）")
    external_item_id = Column(String(64), nullable=True)
    buyer_id = Column(String(120), nullable=True)
    buyer_nick = Column(String(255), nullable=True, comment="买家昵称（脱敏存储）")
    buyer_icon = Column(Text, nullable=True)
    item_title = Column(String(500), nullable=True)
    item_pic_url = Column(Text, nullable=True)
    item_info_lines = Column(Text, nullable=True)
    order_status = Column(String(64), nullable=True)
    seller_rate_status = Column(String(16), nullable=True, comment="卖家评价状态码（原始字符串存储，无确认映射）")
    in_refund = Column(String(16), nullable=True, comment="是否在退款中（原始字符串）")
    consign_time = Column(DateTime, nullable=True)
    order_create_time = Column(DateTime, nullable=True)
    pay_success_time = Column(DateTime, nullable=True)
    finish_time = Column(DateTime, nullable=True)
    logistics_company = Column(String(128), nullable=True)
    logistics_mail_no = Column(String(128), nullable=True, comment="物流单号（脱敏存储）")
    buyer_rate_content = Column(Text, nullable=True, comment="买家评价内容（seller=false 的 feedBack）")
    buyer_rate_level = Column(String(16), nullable=True)
    buyer_rate_time = Column(DateTime, nullable=True)
    buyer_rate_images = Column(Text, nullable=True, comment="买家评价图片列表 JSON")
    seller_rate_content = Column(Text, nullable=True, comment="卖家评价内容（seller=true 的 feedBack）")
    seller_rate_level = Column(String(16), nullable=True)
    seller_rate_time = Column(DateTime, nullable=True)
    seller_rate_images = Column(Text, nullable=True, comment="卖家评价图片列表 JSON")
    seller_rate_id = Column(String(64), nullable=True)
    has_seller_rate = Column(SmallInteger, nullable=False, default=0, comment="1=已存在卖家评价 0=未评价")
    rate_reviewable = Column(SmallInteger, nullable=False, default=0, comment="1=可评价 0=不可评价")
    raw_json = Column(Text, nullable=True, comment="原始响应记录（脱敏后）")
    sync_status = Column(String(32), nullable=False, default="synced", comment="synced=已同步, pending_refresh=待刷新")
    last_synced_time = Column(DateTime, nullable=True, comment="最后一次同步时间（本项目记录时间，不覆盖闲鱼业务时间）")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRateSyncTask(Base):
    """评价同步任务追踪（参考 XianyuRefundSyncTask 模式）。"""
    __tablename__ = "xianyu_rate_sync_task"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sync_id = Column(String(80), nullable=False, unique=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=True, comment="NULL 表示全部账号聚合任务")
    scope = Column(String(20), nullable=False, default="single", comment="single / all")
    status = Column(String(30), nullable=False, default="queued", comment="queued/running/completed/failed")
    progress = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    new_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    succeeded_count = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


class XianyuRateAccountState(Base):
    """账号级评价同步状态：记录最后同步时间、缓存过期判断、任务去重。"""
    __tablename__ = "xianyu_rate_account_state"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, nullable=False)
    account_id = Column(BigInteger, nullable=False)
    last_sync_time = Column(DateTime, nullable=True)
    last_sync_status = Column(String(30), nullable=True, comment="success/failed/partial")
    last_sync_error = Column(String(500), nullable=True)
    last_total_count = Column(Integer, nullable=True)
    is_syncing = Column(SmallInteger, nullable=False, default=0, comment="1=同步中（任务去重）")
    sync_started_time = Column(DateTime, nullable=True)
    last_full_sync_time = Column(DateTime, nullable=True, comment="最后一次完整同步时间")
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


