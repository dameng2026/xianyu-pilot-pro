-- 评价管理功能：评价记录持久化 + 同步任务追踪 + 账号级同步状态
-- 复用 xianyu_account / xianyu_account_auth 现有表，不修改账号表结构
-- 评价记录以 (tenant_id, account_id, external_order_id) 唯一标识，支持多账号聚合
-- 评价记录对应"订单维度"——一个订单只允许一次卖家评价

-- 评价记录表：存储从闲鱼评价列表接口同步的评价管理记录
CREATE TABLE IF NOT EXISTS `xianyu_rate` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '所属闲鱼账号ID',
    `external_order_id` VARCHAR(64) NOT NULL COMMENT '订单ID（merchantCommonData.orderId，字符串存储避免大整数精度丢失）',
    `external_item_id` VARCHAR(64) NULL COMMENT '商品ID（merchantCommonData.itemId，字符串存储）',
    `buyer_id` VARCHAR(120) NULL COMMENT '买家ID（merchantBuyerVO.buyerId，字符串存储）',
    `buyer_nick` VARCHAR(255) NULL COMMENT '买家昵称（merchantBuyerVO.userNick，脱敏存储）',
    `buyer_icon` TEXT NULL COMMENT '买家头像URL（merchantBuyerVO.userIcon）',
    `item_title` VARCHAR(500) NULL COMMENT '商品标题（merchantItemVO.title）',
    `item_pic_url` TEXT NULL COMMENT '商品图片URL（merchantItemVO.itemPicUrl）',
    `item_info_lines` TEXT NULL COMMENT '商品规格补充信息（merchantItemVO.itemInfoLines）',
    `order_status` VARCHAR(64) NULL COMMENT '订单状态（merchantCommonData.orderStatus）',
    `seller_rate_status` VARCHAR(16) NULL COMMENT '卖家评价状态码（merchantCommonData.sellerRateStatus，原始字符串存储，无确认映射）',
    `in_refund` VARCHAR(16) NULL COMMENT '是否在退款中（merchantCommonData.inRefund，原始字符串）',
    `consign_time` DATETIME NULL COMMENT '发货时间（merchantCommonData.consignTime）',
    `order_create_time` DATETIME NULL COMMENT '订单创建时间（merchantCommonData.createTime）',
    `pay_success_time` DATETIME NULL COMMENT '支付成功时间（merchantCommonData.paySuccessTime）',
    `finish_time` DATETIME NULL COMMENT '交易完成时间（merchantCommonData.finishTime）',
    `logistics_company` VARCHAR(128) NULL COMMENT '物流公司（merchantCommonData.companyName）',
    `logistics_mail_no` VARCHAR(128) NULL COMMENT '物流单号（merchantCommonData.mailNo，脱敏存储）',
    `buyer_rate_content` TEXT NULL COMMENT '买家评价内容（rateItemVOList中 seller=false 的 feedBack）',
    `buyer_rate_level` VARCHAR(16) NULL COMMENT '买家评价等级（rateItemVOList中 seller=false 的 rate）',
    `buyer_rate_time` DATETIME NULL COMMENT '买家评价时间（rateItemVOList中 seller=false 的 gmtCreate）',
    `buyer_rate_images` TEXT NULL COMMENT '买家评价图片列表 JSON（rateItemVOList中 seller=false 的 pictCdnUrlList）',
    `seller_rate_content` TEXT NULL COMMENT '卖家评价内容（rateItemVOList中 seller=true 的 feedBack）',
    `seller_rate_level` VARCHAR(16) NULL COMMENT '卖家评价等级（rateItemVOList中 seller=true 的 rate）',
    `seller_rate_time` DATETIME NULL COMMENT '卖家评价时间（rateItemVOList中 seller=true 的 gmtCreate）',
    `seller_rate_images` TEXT NULL COMMENT '卖家评价图片列表 JSON（rateItemVOList中 seller=true 的 pictCdnUrlList）',
    `seller_rate_id` VARCHAR(64) NULL COMMENT '卖家评价ID（rateItemVOList中 seller=true 的 rateId）',
    `has_seller_rate` TINYINT NOT NULL DEFAULT 0 COMMENT '是否已存在卖家评价：1=已评价, 0=未评价（基于 rateItemVOList 中是否存在 seller=true 记录）',
    `rate_reviewable` TINYINT NOT NULL DEFAULT 0 COMMENT '当前订单是否可评价：1=可评价, 0=不可评价（结合 has_seller_rate 与项目订单状态规则）',
    `raw_json` TEXT NULL COMMENT '原始响应记录（脱敏后的评价记录 JSON，用于调试和字段补全）',
    `sync_status` VARCHAR(32) NOT NULL DEFAULT 'synced' COMMENT '同步状态：synced=已同步, pending_refresh=待刷新',
    `last_synced_time` DATETIME(6) NULL COMMENT '最后一次同步时间（本项目记录时间，不覆盖闲鱼业务时间）',
    `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '软删除：评价历史通常不物理删除',
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '本项目记录创建时间',
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '本项目记录更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_rate_tenant_account_order` (`tenant_id`, `account_id`, `external_order_id`),
    KEY `idx_rate_tenant_account` (`tenant_id`, `account_id`, `deleted`),
    KEY `idx_rate_tenant_status` (`tenant_id`, `deleted`, `rate_reviewable`),
    KEY `idx_rate_tenant_time` (`tenant_id`, `deleted`, `finish_time`),
    KEY `idx_rate_sync_status` (`tenant_id`, `account_id`, `sync_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闲鱼评价记录（多账号聚合，按 account_id+external_order_id 唯一）';

-- 评价同步任务追踪表：记录每次评价同步任务的状态（参考 xianyu_refund_sync_task 模式）
CREATE TABLE IF NOT EXISTS `xianyu_rate_sync_task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `sync_id` VARCHAR(80) NOT NULL COMMENT '同步任务ID（唯一）',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NULL COMMENT '账号ID（NULL 表示全部账号聚合任务）',
    `scope` VARCHAR(20) NOT NULL DEFAULT 'single' COMMENT '同步范围：single=单账号, all=全部账号',
    `status` VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '任务状态：queued/running/completed/failed',
    `progress` INT NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
    `total_count` INT NOT NULL DEFAULT 0 COMMENT '本次同步的评价总数',
    `new_count` INT NOT NULL DEFAULT 0 COMMENT '新增评价数',
    `updated_count` INT NOT NULL DEFAULT 0 COMMENT '更新评价数',
    `failed_count` INT NOT NULL DEFAULT 0 COMMENT '失败账号数（全部账号模式）',
    `succeeded_count` INT NOT NULL DEFAULT 0 COMMENT '成功账号数（全部账号模式）',
    `duration_seconds` FLOAT NOT NULL DEFAULT 0 COMMENT '同步耗时（秒）',
    `error_message` TEXT NULL COMMENT '错误信息（脱敏）',
    `started_time` DATETIME(6) NULL COMMENT '开始时间',
    `finished_time` DATETIME(6) NULL COMMENT '完成时间',
    `deleted` TINYINT NOT NULL DEFAULT 0,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_rate_sync_id` (`sync_id`),
    KEY `idx_rate_sync_tenant` (`tenant_id`, `deleted`),
    KEY `idx_rate_sync_account` (`tenant_id`, `account_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评价同步任务追踪';

-- 账号级评价同步状态表：记录每个账号的最后同步时间、缓存过期判断、任务去重
CREATE TABLE IF NOT EXISTS `xianyu_rate_account_state` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
    `last_sync_time` DATETIME(6) NULL COMMENT '最后一次成功同步时间',
    `last_sync_status` VARCHAR(30) NULL COMMENT '最后一次同步状态：success/failed/partial',
    `last_sync_error` VARCHAR(500) NULL COMMENT '最后一次同步错误信息（脱敏）',
    `last_total_count` INT NULL COMMENT '最后一次同步的评价总数',
    `is_syncing` TINYINT NOT NULL DEFAULT 0 COMMENT '是否正在同步（1=同步中，用于任务去重）',
    `sync_started_time` DATETIME(6) NULL COMMENT '当前同步任务开始时间',
    `last_full_sync_time` DATETIME(6) NULL COMMENT '最后一次完整同步时间（用于区分快速刷新和完整校验）',
    `deleted` TINYINT NOT NULL DEFAULT 0,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_rate_state_account` (`tenant_id`, `account_id`),
    KEY `idx_rate_state_syncing` (`tenant_id`, `is_syncing`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号级评价同步状态';
