package com.xianyu.admin.mapper;

import com.xianyu.admin.entity.XianyuTradeOrderItem;
import org.apache.ibatis.annotations.*;

import java.util.List;

@Mapper
public interface XianyuTradeOrderItemMapper {

    @Select("SELECT * FROM xianyu_trade_order_item WHERE tenant_id = #{tenantId} AND order_id = #{orderId} AND deleted = 0 ORDER BY id ASC")
    List<XianyuTradeOrderItem> findByOrderId(@Param("tenantId") Long tenantId, @Param("orderId") Long orderId);

    @Insert("INSERT INTO xianyu_trade_order_item(tenant_id, order_id, goods_id, goods_title, goods_price, goods_count, external_goods_id, deleted, created_time, updated_time) " +
            "VALUES(#{tenantId}, #{orderId}, #{goodsId}, #{goodsTitle}, #{goodsPrice}, #{goodsCount}, #{externalGoodsId}, 0, NOW(), NOW())")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(XianyuTradeOrderItem item);
}
