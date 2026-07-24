package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;
import java.util.Map;

@Mapper
public interface ApiCredentialMapper {

    @Select("SELECT id, tenant_id, api_key_hash, api_key_prefix, api_key_encrypted, enabled, last_used_at, created_time " +
            "FROM xianyu_api_credential WHERE api_key_hash = #{hash} AND enabled = 1")
    Map<String, Object> findByHash(@Param("hash") String hash);

    @Select("SELECT id, tenant_id, api_key_hash, api_key_prefix, api_key_encrypted, enabled, last_used_at, created_time " +
            "FROM xianyu_api_credential WHERE tenant_id = #{tenantId}")
    Map<String, Object> findByTenantId(@Param("tenantId") Long tenantId);

    @Update("UPDATE xianyu_api_credential SET api_key_hash = #{hash}, api_key_prefix = #{prefix}, api_key_encrypted = #{encrypted}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId}")
    int updateCredential(@Param("tenantId") Long tenantId, @Param("hash") String hash, @Param("prefix") String prefix, @Param("encrypted") String encrypted);

    @Update("UPDATE xianyu_api_credential SET last_used_at = NOW() WHERE tenant_id = #{tenantId}")
    int touchLastUsed(@Param("tenantId") Long tenantId);

    @Select("SELECT tenant_id FROM xianyu_api_credential WHERE enabled = 1")
    List<Long> findAllTenantsWithCredentials();

    @Update("INSERT INTO xianyu_api_credential_reset_operation (operation_key, status, created_time, updated_time) " +
            "VALUES (#{operationKey}, 'pending', NOW(), NOW()) ON DUPLICATE KEY UPDATE operation_key = operation_key")
    int ensureFullResetOperation(@Param("operationKey") String operationKey);

    @Select("SELECT operation_key, status FROM xianyu_api_credential_reset_operation WHERE operation_key = #{operationKey} FOR UPDATE")
    Map<String, Object> findFullResetOperationForUpdate(@Param("operationKey") String operationKey);

    @Update("UPDATE xianyu_api_credential_reset_operation SET status = 'completed', completed_time = NOW(), updated_time = NOW() " +
            "WHERE operation_key = #{operationKey} AND status = 'pending'")
    int markFullResetCompleted(@Param("operationKey") String operationKey);

    @Update("INSERT INTO xianyu_api_credential (tenant_id, api_key_hash, api_key_prefix, api_key_encrypted, enabled, created_time, updated_time) " +
            "VALUES (#{tenantId}, #{hash}, #{prefix}, #{encrypted}, 1, NOW(), NOW()) " +
            "ON DUPLICATE KEY UPDATE api_key_hash = #{hash}, api_key_prefix = #{prefix}, api_key_encrypted = #{encrypted}, updated_time = NOW()")
    int upsertCredential(@Param("tenantId") Long tenantId, @Param("hash") String hash, @Param("prefix") String prefix, @Param("encrypted") String encrypted);
}
