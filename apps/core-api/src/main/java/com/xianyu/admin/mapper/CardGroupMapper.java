package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.CardGroup;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface CardGroupMapper {

    @Select("<script>" +
            "SELECT * FROM card_group " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (group_name LIKE CONCAT('%', #{keyword}, '%') OR description LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "ORDER BY created_time DESC " +
            "LIMIT #{offset}, #{limit}" +
            "</script>")
    List<CardGroup> list(@Param("tenantId") Long tenantId,
                         @Param("keyword") String keyword,
                         @Param("offset") int offset,
                         @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM card_group " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 " +
            "<if test='keyword != null and keyword != \"\"'>" +
            "  AND (group_name LIKE CONCAT('%', #{keyword}, '%') OR description LIKE CONCAT('%', #{keyword}, '%')) " +
            "</if>" +
            "</script>")
    int count(@Param("tenantId") Long tenantId, @Param("keyword") String keyword);

    @Select("SELECT * FROM card_group WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    CardGroup findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO card_group(tenant_id, group_name, description, group_type, card_prefix, password_prefix, remark, alert_threshold, cost_price, suggested_price, total_count, used_count, remain_count, available_count, sku_property_key, status, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{groupName}, #{description}, #{groupType}, #{cardPrefix}, #{passwordPrefix}, #{remark}, #{alertThreshold}, #{costPrice}, #{suggestedPrice}, #{totalCount}, #{usedCount}, #{remainCount}, #{remainCount}, #{skuPropertyKey}, #{status}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(CardGroup group);

    @Update("UPDATE card_group SET group_name = #{groupName}, description = #{description}, group_type = #{groupType}, " +
            "card_prefix = #{cardPrefix}, password_prefix = #{passwordPrefix}, remark = #{remark}, " +
            "alert_threshold = #{alertThreshold}, cost_price = #{costPrice}, suggested_price = #{suggestedPrice}, " +
            "total_count = #{totalCount}, used_count = #{usedCount}, remain_count = #{remainCount}, available_count = #{remainCount}, " +
            "sku_property_key = #{skuPropertyKey}, status = #{status}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(CardGroup group);

    @Update("UPDATE card_group SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Update("UPDATE card_group SET " +
            "total_count = (SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0), " +
            "used_count = (SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = 2), " +
            "remain_count = (SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = 0), " +
            "available_count = (SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = 0), " +
            "updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{groupId} AND deleted = 0")
    int refreshCounts(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);
}
