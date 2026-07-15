package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuAccountMembership;
import org.apache.ibatis.annotations.*;

@Mapper
public interface XianyuAccountMembershipMapper {

    @Select("SELECT * FROM xianyu_account_membership WHERE tenant_id = #{tenantId} AND account_id = #{accountId} LIMIT 1")
    XianyuAccountMembership findByAccountId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Insert("INSERT INTO xianyu_account_membership(tenant_id, account_id, level, expired_time, status, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{membershipLevel}, #{expiredTime}, #{status}, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuAccountMembership membership);

    @Update("UPDATE xianyu_account_membership SET level = #{membershipLevel}, expired_time = #{expiredTime}, " +
            "status = #{status}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id}")
    int update(XianyuAccountMembership membership);
}
