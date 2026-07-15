package com.xianyu.admin.dto;

import java.math.BigDecimal;

/**
 * 闲鱼交易订单项VO
 */
public class XianyuTradeOrderItemVO {
    private Long id;
    private Long orderId;
    private String goodsTitle;
    private String goodsImage;
    private BigDecimal goodsPrice;
    private Integer goodsCount;
    private String specName;
    private String specValue;
    private String specSummary;
    private String externalGoodsId;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getOrderId() { return orderId; }
    public void setOrderId(Long orderId) { this.orderId = orderId; }
    public String getGoodsTitle() { return goodsTitle; }
    public void setGoodsTitle(String goodsTitle) { this.goodsTitle = goodsTitle; }
    public String getGoodsImage() { return goodsImage; }
    public void setGoodsImage(String goodsImage) { this.goodsImage = goodsImage; }
    public BigDecimal getGoodsPrice() { return goodsPrice; }
    public void setGoodsPrice(BigDecimal goodsPrice) { this.goodsPrice = goodsPrice; }
    public Integer getGoodsCount() { return goodsCount; }
    public void setGoodsCount(Integer goodsCount) { this.goodsCount = goodsCount; }
    public String getSpecName() { return specName; }
    public void setSpecName(String specName) { this.specName = specName; }
    public String getSpecValue() { return specValue; }
    public void setSpecValue(String specValue) { this.specValue = specValue; }
    public String getSpecSummary() { return specSummary; }
    public void setSpecSummary(String specSummary) { this.specSummary = specSummary; }
    public String getExternalGoodsId() { return externalGoodsId; }
    public void setExternalGoodsId(String externalGoodsId) { this.externalGoodsId = externalGoodsId; }
}
