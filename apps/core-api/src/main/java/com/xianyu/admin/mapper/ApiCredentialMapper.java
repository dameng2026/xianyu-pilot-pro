package com.xianyu.admin.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.Map;

@Mapper
public interface ApiCredentialMapper {

    @Select("SELECT id, tenant_id, api_key_hash, api_key_prefix, enabled, last_used_at, created_time " +
            "FROM xianyu_api_credential WHERE api_key_hash = #{hash} AND enabled = 1")
    Map<String, Object> findByHash(@Param("hash") String hash);

    @Select("SELECT id, tenant_id, api_key_hash, api_key_prefix, enabled, last_used_at, created_time " +
            "FROM xianyu_api_credential WHERE tenant_id = #{tenantId}")
    Map<String, Object> findByTenantId(@Param("tenantId") Long tenantId);

    @Update("UPDATE xianyu_api_credential SET api_key_hash = #{hash}, api_key_prefix = #{prefix}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId}")
    int updateCredential(@Param("tenantId") Long tenantId, @Param("hash") String hash, @Param("prefix") String prefix);

    @Update("UPDATE xianyu_api_credential SET last_used_at = NOW() WHERE tenant_id = #{tenantId}")
    int touchLastUsed(@Param("tenantId") Long tenantId);

    @Update("INSERT INTO xianyu_api_credential (tenant_id, api_key_hash, api_key_prefix, enabled, created_time, updated_time) " +
            "VALUES (#{tenantId}, #{hash}, #{prefix}, 1, NOW(), NOW()) " +
            "ON DUPLICATE KEY UPDATE api_key_hash = #{hash}, api_key_prefix = #{prefix}, updated_time = NOW()")
    int upsertCredential(@Param("tenantId") Long tenantId, @Param("hash") String hash, @Param("prefix") String prefix);
}
