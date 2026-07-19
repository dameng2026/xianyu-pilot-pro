-- V1.25: 为 opportunity_image_history 增加生图来源字段，区分商机发掘与工作流
ALTER TABLE opportunity_image_history
  ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'opportunity'
    COMMENT '生图来源：opportunity=商机发掘 / workflow=工作流',
  ADD COLUMN workflow_id BIGINT NULL COMMENT '工作流定义ID（source=workflow 时）',
  ADD COLUMN workflow_execution_id BIGINT NULL COMMENT '工作流执行记录ID（source=workflow 时）',
  ADD COLUMN workflow_node_key VARCHAR(100) NULL COMMENT '生图节点key（source=workflow 时）',
  ADD INDEX idx_oih_source_tenant_created (source, tenant_id, created_time DESC);
