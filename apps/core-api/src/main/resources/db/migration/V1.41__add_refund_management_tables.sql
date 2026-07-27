-- 注：core-api 不使用 Flyway 框架，本文件为文档性质；
-- 实际表结构变更由 SchemaCompatibilityRunner 在启动时幂等创建。
-- 与 automation-service/migrations/V1.22__add_refund_management_tables.sql 保持一致。

-- 退款管理功能：退款记录持久化 + 同步任务追踪 + 账号级同步状态
-- 复用 xianyu_account / xianyu_account_auth 现有表，不修改账号表结构
-- 退款记录以 (tenant_id, account_id, external_refund_id) 唯一标识，支持多账号聚合
-- 仅鱼小铺账号（fish_shop_user=1）允许调用退款接口

CREATE TABLE IF NOT EXISTS `xianyu_refund` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '所属闲鱼账号ID',
    `external_refund_id` VARCHAR(64) NOT NULL COMMENT '闲鱼退款ID（refundInfoVO.refundId，字符串存储避免大整数精度丢失）',
    `external_order_id` VARCHAR(64) NULL COMMENT '订单ID（commonData.orderId，字符串存储）',
    `external_item_id` VARCHAR(64) NULL COMMENT '商品ID（commonData.itemId，字符串存储）',
    `item_title` VARCHAR(500) NULL COMMENT '商品标题（itemVO.title）',
    `item_pic_url` TEXT NULL COMMENT '商品图片URL（itemVO.itemPicUrl）',
    `item_info_lines` TEXT NULL COMMENT '商品规格补充信息（itemVO.itemInfoLines）',
    `buy_num` VARCHAR(32) NULL COMMENT '购买件数（priceVO.buyNum，保留原始字符串）',
    `refund_fee` DECIMAL(18,4) NULL COMMENT '退款金额（priceVO.refundFee，十进制存储避免浮点误差）',
    `auction_price` DECIMAL(18,4) NULL COMMENT '商品成交单价（priceVO.auctionPrice）',
    `order_status` VARCHAR(64) NULL COMMENT '退款大类（commonData.orderStatus，如：未发货退款/已发货退款/退货退款）',
    `order_simple_remark` VARCHAR(255) NULL COMMENT '订单退款简要状态（commonData.orderSimpleRemark）',
    `refund_status` VARCHAR(64) NULL COMMENT '退款详细状态（refundInfoVO.refundStatus）',
    `refund_status_desc` VARCHAR(500) NULL COMMENT '状态倒计时或补充说明（refundInfoVO.refundStatusDesc）',
    `common_refund_status` VARCHAR(64) NULL COMMENT '服务端状态代码（commonData.refundStatus）',
    `refund_reason` VARCHAR(500) NULL COMMENT '退款原因（refundInfoVO.reason）',
    `cs_status` VARCHAR(64) NULL COMMENT '客服介入状态（refundInfoVO.csStatus）',
    `logistics_company` VARCHAR(128) NULL COMMENT '物流公司（commonData.companyName）',
    `logistics_mail_no` VARCHAR(128) NULL COMMENT '物流单号（commonData.mailNo，脱敏存储）',
    `consign_time` DATETIME NULL COMMENT '发货时间（commonData.consignTime）',
    `refund_create_time` DATETIME NULL COMMENT '退款申请时间（refundInfoVO.gmtCreate）',
    `common_create_time` DATETIME NULL COMMENT '订单创建时间回退字段（commonData.createTime）',
    `buyer_nick` VARCHAR(255) NULL COMMENT '买家昵称（buyerInfoVO.userNick，脱敏存储）',
    `right_buttons_json` TEXT NULL COMMENT '操作按钮列表（rightVO.btnList 的 JSON，用于动态渲染操作列）',
    `ext_total_refund_fee` DECIMAL(18,4) NULL COMMENT '当前查询范围的退款总金额（data.data.ext.totalRefundFee，仅单账号有意义）',
    `raw_json` TEXT NULL COMMENT '原始响应记录（脱敏后的退款记录 JSON，用于调试和字段补全）',
    `sync_status` VARCHAR(32) NOT NULL DEFAULT 'synced' COMMENT '同步状态：synced=已同步, pending_refresh=待刷新',
    `last_synced_time` DATETIME(6) NULL COMMENT '最后一次同步时间',
    `deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '软删除：退款历史通常不物理删除',
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_refund_tenant_account_external` (`tenant_id`, `account_id`, `external_refund_id`),
    KEY `idx_refund_tenant_account` (`tenant_id`, `account_id`, `deleted`),
    KEY `idx_refund_tenant_status` (`tenant_id`, `deleted`, `order_status`),
    KEY `idx_refund_tenant_time` (`tenant_id`, `deleted`, `refund_create_time`),
    KEY `idx_refund_sync_status` (`tenant_id`, `account_id`, `sync_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='闲鱼退款记录（多账号聚合，按 account_id+external_refund_id 唯一）';

CREATE TABLE IF NOT EXISTS `xianyu_refund_sync_task` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `sync_id` VARCHAR(80) NOT NULL COMMENT '同步任务ID（唯一）',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NULL COMMENT '账号ID（NULL 表示全部账号聚合任务）',
    `scope` VARCHAR(20) NOT NULL DEFAULT 'single' COMMENT '同步范围：single=单账号, all=全部账号',
    `status` VARCHAR(30) NOT NULL DEFAULT 'queued' COMMENT '任务状态：queued/running/completed/failed',
    `progress` INT NOT NULL DEFAULT 0 COMMENT '进度百分比 0-100',
    `total_count` INT NOT NULL DEFAULT 0 COMMENT '本次同步的退款总数',
    `new_count` INT NOT NULL DEFAULT 0 COMMENT '新增退款数',
    `updated_count` INT NOT NULL DEFAULT 0 COMMENT '更新退款数',
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
    UNIQUE KEY `uk_refund_sync_id` (`sync_id`),
    KEY `idx_refund_sync_tenant` (`tenant_id`, `deleted`),
    KEY `idx_refund_sync_account` (`tenant_id`, `account_id`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='退款同步任务追踪';

CREATE TABLE IF NOT EXISTS `xianyu_refund_account_state` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
    `account_id` BIGINT NOT NULL COMMENT '闲鱼账号ID',
    `last_sync_time` DATETIME(6) NULL COMMENT '最后一次成功同步时间',
    `last_sync_status` VARCHAR(30) NULL COMMENT '最后一次同步状态：success/failed/partial',
    `last_sync_error` VARCHAR(500) NULL COMMENT '最后一次同步错误信息（脱敏）',
    `last_total_count` INT NULL COMMENT '最后一次同步的退款总数',
    `is_syncing` TINYINT NOT NULL DEFAULT 0 COMMENT '是否正在同步（1=同步中，用于任务去重）',
    `sync_started_time` DATETIME(6) NULL COMMENT '当前同步任务开始时间',
    `last_full_sync_time` DATETIME(6) NULL COMMENT '最后一次完整同步时间（用于区分快速刷新和完整校验）',
    `deleted` TINYINT NOT NULL DEFAULT 0,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_refund_state_account` (`tenant_id`, `account_id`),
    KEY `idx_refund_state_syncing` (`tenant_id`, `is_syncing`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号级退款同步状态';
