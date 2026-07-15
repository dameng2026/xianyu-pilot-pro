-- 中国地址字典表（全国省市区县）
-- 本地存储全国行政区划与区县级发布定位信息
-- 闲鱼发布所需 8 字段：prov/city/area/divisionId/gps/poiId/poiName/detail 全部落库
CREATE TABLE IF NOT EXISTS china_address_dict (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    adcode VARCHAR(12) NOT NULL COMMENT '区县级行政区划代码',
    prov VARCHAR(50) NOT NULL DEFAULT '' COMMENT '省/直辖市',
    city VARCHAR(50) NOT NULL DEFAULT '' COMMENT '市',
    area VARCHAR(50) NOT NULL DEFAULT '' COMMENT '区/县',
    full_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '完整名称 省+市+区(如 河南省郑州市中原区)',
    division_id VARCHAR(20) NOT NULL DEFAULT '' COMMENT '闲鱼 divisionId(=adcode)',
    gps VARCHAR(40) NOT NULL DEFAULT '' COMMENT '经纬度 lng,lat(优先取 POI location)',
    gps_center VARCHAR(40) NOT NULL DEFAULT '' COMMENT '区中心点经纬度(行政区划 center, 兜底用)',
    poi_id VARCHAR(40) NOT NULL DEFAULT '' COMMENT '发布定位 POI ID',
    poi_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT 'POI 名称(如 中原区人民政府)',
    detail VARCHAR(300) NOT NULL DEFAULT '' COMMENT '详细地址',
    sync_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '同步状态 pending/success/failed',
    error_msg VARCHAR(500) NOT NULL DEFAULT '' COMMENT '失败原因',
    retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_cad_adcode (adcode),
    INDEX idx_cad_prov_city (prov, city),
    INDEX idx_cad_sync_status (sync_status),
    INDEX idx_cad_full_name (full_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中国地址字典(全国省市区县)';
