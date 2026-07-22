package com.xianyu.admin.dto;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 闲鱼交易订单VO
 */
public class XianyuTradeOrderVO {
    private Long id;
    private Long accountId;
    private String externalOrderId;
    private Integer orderStatus;
    private BigDecimal totalAmount;
    private String buyerName;
    private String buyerId;
    private LocalDateTime createTime;
    private LocalDateTime payTime;
    private LocalDateTime shipTime;
    private String itemSummary;
    private String sellerRemark;
    private Integer quantityTotal;
    private String deliveryMethod;
    private String deliveryStatus;
    private String deliveryFailReason;
    private String deliveryContent;
    private Integer quantityRequested;
    private Integer quantitySent;
    private LocalDateTime platformSyncTime;
    private String itemId;
    private Boolean isBargain;
    private Boolean isRated;
    private Boolean isRedFlower;
    private List<XianyuTradeOrderItemVO> items;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getExternalOrderId() { return externalOrderId; }
    public void setExternalOrderId(String externalOrderId) { this.externalOrderId = externalOrderId; }
    public Integer getOrderStatus() { return orderStatus; }
    public void setOrderStatus(Integer orderStatus) { this.orderStatus = orderStatus; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public void setTotalAmount(BigDecimal totalAmount) { this.totalAmount = totalAmount; }
    public String getBuyerName() { return buyerName; }
    public void setBuyerName(String buyerName) { this.buyerName = buyerName; }
    public String getBuyerId() { return buyerId; }
    public void setBuyerId(String buyerId) { this.buyerId = buyerId; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getPayTime() { return payTime; }
    public void setPayTime(LocalDateTime payTime) { this.payTime = payTime; }
    public LocalDateTime getShipTime() { return shipTime; }
    public void setShipTime(LocalDateTime shipTime) { this.shipTime = shipTime; }
    public String getItemSummary() { return itemSummary; }
    public void setItemSummary(String itemSummary) { this.itemSummary = itemSummary; }
    public String getSellerRemark() { return sellerRemark; }
    public void setSellerRemark(String sellerRemark) { this.sellerRemark = sellerRemark; }
    public Integer getQuantityTotal() { return quantityTotal; }
    public void setQuantityTotal(Integer quantityTotal) { this.quantityTotal = quantityTotal; }
    public String getDeliveryMethod() { return deliveryMethod; }
    public void setDeliveryMethod(String deliveryMethod) { this.deliveryMethod = deliveryMethod; }
    public String getDeliveryStatus() { return deliveryStatus; }
    public void setDeliveryStatus(String deliveryStatus) { this.deliveryStatus = deliveryStatus; }
    public String getDeliveryFailReason() { return deliveryFailReason; }
    public void setDeliveryFailReason(String deliveryFailReason) { this.deliveryFailReason = deliveryFailReason; }
    public String getDeliveryContent() { return deliveryContent; }
    public void setDeliveryContent(String deliveryContent) { this.deliveryContent = deliveryContent; }
    public Integer getQuantityRequested() { return quantityRequested; }
    public void setQuantityRequested(Integer quantityRequested) { this.quantityRequested = quantityRequested; }
    public Integer getQuantitySent() { return quantitySent; }
    public void setQuantitySent(Integer quantitySent) { this.quantitySent = quantitySent; }
    public LocalDateTime getPlatformSyncTime() { return platformSyncTime; }
    public void setPlatformSyncTime(LocalDateTime platformSyncTime) { this.platformSyncTime = platformSyncTime; }
    public List<XianyuTradeOrderItemVO> getItems() { return items; }
    public void setItems(List<XianyuTradeOrderItemVO> items) { this.items = items; }
    public String getItemId() { return itemId; }
    public void setItemId(String itemId) { this.itemId = itemId; }
    public Boolean getIsBargain() { return isBargain; }
    public void setIsBargain(Boolean isBargain) { this.isBargain = isBargain; }
    public Boolean getIsRated() { return isRated; }
    public void setIsRated(Boolean isRated) { this.isRated = isRated; }
    public Boolean getIsRedFlower() { return isRedFlower; }
    public void setIsRedFlower(Boolean isRedFlower) { this.isRedFlower = isRedFlower; }
}
