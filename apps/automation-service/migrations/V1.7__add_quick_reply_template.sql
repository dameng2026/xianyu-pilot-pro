-- 快捷回复模板表
-- 与 auto_reply_rule 解耦，专用于"人工点击即插入到输入框"的常用语
CREATE TABLE IF NOT EXISTS `quick_reply_template` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `tenant_id` BIGINT NOT NULL COMMENT '租户ID',
  `account_id` BIGINT DEFAULT NULL COMMENT '闲鱼账号ID，NULL表示全租户通用',
  `title` VARCHAR(200) NOT NULL COMMENT '模板标题',
  `content` TEXT NOT NULL COMMENT '模板内容',
  `sort_order` INT DEFAULT 0 COMMENT '排序，越小越靠前',
  `status` TINYINT DEFAULT 1 COMMENT '1启用 0禁用',
  `deleted` TINYINT DEFAULT 0 COMMENT '0未删除 1已删除',
  `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_qrt_tenant_account` (`tenant_id`, `account_id`, `deleted`),
  INDEX `idx_qrt_sort` (`tenant_id`, `deleted`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='快捷回复模板表';

-- 默认 10 条快捷回复模板（tenant_id=1 为默认租户，account_id=NULL 表示全租户通用）
INSERT INTO `quick_reply_template` (`tenant_id`, `account_id`, `title`, `content`, `sort_order`, `status`, `deleted`)
VALUES
  (1, NULL, '亲切问候', '您好，很高兴为您服务！有什么可以帮您的吗？', 1, 1, 0),
  (1, NULL, '商品咨询', '这款商品目前有货的，您可以放心下单，我们会在24小时内发货。', 2, 1, 0),
  (1, NULL, '价格说明', '亲，这是我们的实价哦，品质保证，性价比很高。如需优惠可以关注店铺活动~', 3, 1, 0),
  (1, NULL, '发货时效', '下单后我们会在24小时内安排发货，一般2-3天可以送达，请耐心等待~', 4, 1, 0),
  (1, NULL, '物流查询', '您好，我帮您查一下物流信息，请稍等。如有问题随时联系我们。', 5, 1, 0),
  (1, NULL, '售后保障', '我们提供7天无理由退换货服务，商品有质量问题可以随时联系我们处理。', 6, 1, 0),
  (1, NULL, '催付提醒', '亲，您看中的宝贝还没下单哦，库存有限，喜欢就尽快下单吧~', 7, 1, 0),
  (1, NULL, '结束语', '感谢您的咨询，祝您生活愉快！如有其他问题欢迎随时联系我们~', 8, 1, 0),
  (1, NULL, '议价回复', '亲，我们的价格已经很实惠了，但您可以关注店铺后续活动，会有更多优惠哦~', 9, 1, 0),
  (1, NULL, '加微引导', '抱歉亲，平台规定不能交换联系方式哦，有问题可以在这里直接沟通，我们会尽快回复您~', 10, 1, 0)
ON DUPLICATE KEY UPDATE `id` = `id`;
