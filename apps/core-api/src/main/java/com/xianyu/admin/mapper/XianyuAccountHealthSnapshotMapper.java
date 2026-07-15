package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuAccountHealthSnapshot;
import org.apache.ibatis.annotations.*;

@Mapper
public interface XianyuAccountHealthSnapshotMapper {

    @Select("SELECT * FROM xianyu_account_health_snapshot WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND deleted = 0 ORDER BY collected_time DESC LIMIT 1")
    XianyuAccountHealthSnapshot findLatestByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Insert("INSERT INTO xianyu_account_health_snapshot(tenant_id, account_id, health_score, api_success_rate, avg_response_ms, ws_latency_ms, collected_time, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{healthScore}, #{apiSuccessRate}, #{avgResponseMs}, #{wsLatencyMs}, #{collectedTime}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuAccountHealthSnapshot snapshot);
}
