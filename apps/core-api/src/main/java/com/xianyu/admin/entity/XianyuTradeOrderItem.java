package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

/**
 * 闲鱼交易订单项实体
 */
@Entity
@Table(name = "xianyu_trade_order_item")
public class XianyuTradeOrderItem extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_id")
    private Long orderId;

    @Column(name = "goods_id")
    private Long goodsId;

    @Column(name = "goods_title")
    private String goodsTitle;

    @Column(name = "goods_price")
    private BigDecimal goodsPrice;

    @Column(name = "goods_count")
    private Integer goodsCount;

    @Column(name = "spec_name")
    private String specName;

    @Column(name = "spec_value")
    private String specValue;

    @Column(name = "external_goods_id")
    private String externalGoodsId;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getOrderId() {
        return orderId;
    }

    public void setOrderId(Long orderId) {
        this.orderId = orderId;
    }

    public Long getGoodsId() {
        return goodsId;
    }

    public void setGoodsId(Long goodsId) {
        this.goodsId = goodsId;
    }

    public String getGoodsTitle() {
        return goodsTitle;
    }

    public void setGoodsTitle(String goodsTitle) {
        this.goodsTitle = goodsTitle;
    }

    public BigDecimal getGoodsPrice() {
        return goodsPrice;
    }

    public void setGoodsPrice(BigDecimal goodsPrice) {
        this.goodsPrice = goodsPrice;
    }

    public Integer getGoodsCount() {
        return goodsCount;
    }

    public void setGoodsCount(Integer goodsCount) {
        this.goodsCount = goodsCount;
    }

    public String getSpecName() {
        return specName;
    }

    public void setSpecName(String specName) {
        this.specName = specName;
    }

    public String getSpecValue() {
        return specValue;
    }

    public void setSpecValue(String specValue) {
        this.specValue = specValue;
    }

    public String getExternalGoodsId() {
        return externalGoodsId;
    }

    public void setExternalGoodsId(String externalGoodsId) {
        this.externalGoodsId = externalGoodsId;
    }
}
