-- V1.26: 套餐表新增自定义介绍文本与周期类型字段
-- features_text: 后台自定义套餐介绍文本（换行分隔多条权益），为空时回退到功能开关生成的默认权益
-- period_type: 周期类型（month=月 / quarter=季 / year=年），前台按周期分组展示套餐
ALTER TABLE billing_plan
  ADD COLUMN features_text TEXT NULL COMMENT '自定义套餐介绍文本（换行分隔多条权益），为空时使用默认功能开关生成的权益描述',
  ADD COLUMN period_type VARCHAR(20) NOT NULL DEFAULT 'month' COMMENT '周期类型：month=月套餐 / quarter=季套餐 / year=年套餐';
