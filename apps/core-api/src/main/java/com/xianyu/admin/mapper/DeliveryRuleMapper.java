package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.DeliveryRule;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface DeliveryRuleMapper {

    @Select("<script>SELECT * FROM delivery_rule WHERE tenant_id = #{tenantId} AND deleted = 0 <if test='accountId != null'> AND account_id = #{accountId} </if> ORDER BY created_time DESC LIMIT #{offset}, #{limit}</script>")
    List<DeliveryRule> list(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("offset") int offset, @Param("limit") int limit);

    @Select("<script>SELECT COUNT(*) FROM delivery_rule WHERE tenant_id = #{tenantId} AND deleted = 0 <if test='accountId != null'> AND account_id = #{accountId} </if></script>")
    int count(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId);

    @Select("SELECT * FROM delivery_rule WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    DeliveryRule findById(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Insert("INSERT INTO delivery_rule(tenant_id, account_id, goods_id, rule_name, delivery_type, card_group_id, delivery_content, trigger_keyword, status, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{accountId}, #{goodsId}, #{ruleName}, #{deliveryType}, #{cardGroupId}, #{deliveryContent}, #{triggerKeyword}, #{status}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(DeliveryRule rule);

    @Update("UPDATE delivery_rule SET account_id = #{accountId}, goods_id = #{goodsId}, rule_name = #{ruleName}, delivery_type = #{deliveryType}, " +
            "card_group_id = #{cardGroupId}, delivery_content = #{deliveryContent}, trigger_keyword = #{triggerKeyword}, status = #{status}, updated_time = NOW() " +
            "WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int update(DeliveryRule rule);

    @Update("UPDATE delivery_rule SET deleted = 1, updated_time = NOW() WHERE tenant_id = #{tenantId} AND id = #{id} AND deleted = 0")
    int softDelete(@Param("tenantId") Long tenantId, @Param("id") Long id);

    @Select("SELECT * FROM delivery_rule WHERE tenant_id = #{tenantId} AND account_id = #{accountId} AND goods_id = #{goodsId} AND deleted = 0 LIMIT 1")
    DeliveryRule findByAccountIdAndGoodsId(@Param("tenantId") Long tenantId, @Param("accountId") Long accountId, @Param("goodsId") Long goodsId);
}
