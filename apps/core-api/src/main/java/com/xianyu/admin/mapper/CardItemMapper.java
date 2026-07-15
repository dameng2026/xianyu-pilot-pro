package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.CardItem;
import org.apache.ibatis.annotations.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface CardItemMapper {

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = #{status} ORDER BY created_time ASC LIMIT #{offset}, #{limit}")
    List<CardItem> listByGroupId(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("status") Integer status, @Param("offset") int offset, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = #{status}")
    int countByGroupId(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("status") Integer status);

    @Select("<script>" +
            "SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 " +
            "<if test='status != null'> AND status = #{status} </if>" +
            "ORDER BY created_time ASC LIMIT #{offset}, #{limit}" +
            "</script>")
    List<CardItem> listByGroupIdAndStatus(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("status") Integer status, @Param("offset") int offset, @Param("limit") int limit);

    @Select("<script>" +
            "SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 " +
            "<if test='status != null'> AND status = #{status} </if>" +
            "</script>")
    int countByGroupIdAndStatus(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("status") Integer status);

    @Insert("INSERT INTO card_item(tenant_id, group_id, card_content, card_key, card_value, extra_info, is_used, status, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{groupId}, #{cardContent}, #{cardKey}, #{cardValue}, #{extraInfo}, 0, #{status}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(CardItem item);

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND status = 0 AND deleted = 0 LIMIT 1")
    CardItem findUnusedOne(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);

    @Update("UPDATE card_item SET status = #{status}, is_used = CASE WHEN #{status} = 2 THEN 1 ELSE 0 END, used_order_id = #{usedOrderId}, used_by_order_id = #{usedOrderId}, used_time = #{usedTime}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0 AND status = 0")
    int updateStatus(@Param("tenantId") Long tenantId, @Param("id") Long id, @Param("status") Integer status, @Param("usedOrderId") Long usedOrderId, @Param("usedTime") LocalDateTime usedTime);

    @Update("UPDATE card_item SET status = 1, is_used = 0, used_order_id = #{orderId}, used_by_order_id = #{orderId}, used_time = NOW(), updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND deleted = 0 AND status = 0 AND group_id = #{groupId} " +
            "ORDER BY id ASC LIMIT 1")
    int claimUnusedOne(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("orderId") Long orderId);

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND (used_order_id = #{orderId} OR used_by_order_id = #{orderId}) AND deleted = 0 ORDER BY used_time DESC, id DESC LIMIT 1")
    CardItem findClaimedByOrder(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("orderId") Long orderId);

    @Select("SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND (card_content = #{content} OR card_key = #{content}) AND deleted = 0")
    int countDuplicateContent(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("content") String content);

    @Update("UPDATE card_item SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("id") Long id);

    @Update("UPDATE card_item SET status = 0, is_used = 0, used_order_id = NULL, used_by_order_id = NULL, used_time = NULL, updated_time = NOW() WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND id = #{id} AND deleted = 0 AND status IN (1,2,4)")
    int reset(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("id") Long id);

    @Update("UPDATE card_item SET status = #{status}, is_used = CASE WHEN #{status} = 2 THEN 1 ELSE 0 END, updated_time = NOW() WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND id = #{id} AND deleted = 0")
    int updateStatusOnly(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("id") Long id, @Param("status") Integer status);

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND id = #{id} AND deleted = 0 LIMIT 1")
    CardItem findById(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("id") Long id);

    @Select("SELECT COUNT(*) AS totalCount, " +
            "SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) AS remainCount, " +
            "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS lockedCount, " +
            "SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) AS usedCount, " +
            "SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END) AS invalidCount, " +
            "SUM(CASE WHEN status = 4 THEN 1 ELSE 0 END) AS errorCount " +
            "FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0")
    Map<String, Object> statsByGroup(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);

    @Select("<script>" +
            "SELECT group_id, " +
            "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS lockedCount, " +
            "SUM(CASE WHEN status = 3 THEN 1 ELSE 0 END) AS invalidCount, " +
            "SUM(CASE WHEN status = 4 THEN 1 ELSE 0 END) AS errorCount " +
            "FROM card_item WHERE tenant_id = #{tenantId} AND deleted = 0 AND group_id IN " +
            "<foreach item='gid' collection='groupIds' open='(' separator=',' close=')'>#{gid}</foreach> " +
            "GROUP BY group_id" +
            "</script>")
    List<Map<String, Object>> statsByGroupIds(@Param("tenantId") Long tenantId, @Param("groupIds") List<Long> groupIds);

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = 2 ORDER BY used_time DESC, id DESC LIMIT #{offset}, #{limit}")
    List<CardItem> listUsedByGroup(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("SELECT COUNT(*) FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 AND status = 2")
    int countUsedByGroup(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);

    @Select("SELECT * FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0 ORDER BY id ASC")
    List<CardItem> listAllByGroup(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);

    @Select("SELECT COALESCE(SUM(OCTET_LENGTH(COALESCE(card_content,'')) + "
            + "OCTET_LENGTH(COALESCE(card_key,'')) + OCTET_LENGTH(COALESCE(card_value,'')) + 6),0) "
            + "FROM card_item WHERE tenant_id = #{tenantId} AND group_id = #{groupId} AND deleted = 0")
    Long estimateExportBytes(@Param("tenantId") Long tenantId, @Param("groupId") Long groupId);
}
