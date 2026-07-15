package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 闲鱼商品VO
 */
public class XianyuGoodsVO {
    private Long id;
    private Long tenantId;
    private Long accountId;
    private String externalGoodsId;
    private String title;
    private String price;
    private String soldPrice;
    private String coverPic;
    private String imageUrl;
    private String stock;
    private Integer quantity;
    private Integer exposureCount;
    private Integer viewCount;
    private Integer wantCount;
    private String detailUrl;
    private String detailInfo;
    private String description;
    private String category;
    private Integer sortOrder;
    private Integer status;
    private LocalDateTime createdTime;
    private LocalDateTime updatedTime;
    private Integer skuCount;
    private Integer autoDeliveryType;
    private Integer xianyuAutoDeliveryOn;
    private Integer xianyuAutoReplyOn;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getExternalGoodsId() { return externalGoodsId; }
    public void setExternalGoodsId(String externalGoodsId) { this.externalGoodsId = externalGoodsId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getPrice() { return price; }
    public void setPrice(String price) { this.price = price; }
    public String getSoldPrice() { return soldPrice; }
    public void setSoldPrice(String soldPrice) { this.soldPrice = soldPrice; }
    public String getCoverPic() { return coverPic; }
    public void setCoverPic(String coverPic) { this.coverPic = coverPic; }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl; }
    public String getStock() { return stock; }
    public void setStock(String stock) { this.stock = stock; }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }
    public Integer getExposureCount() { return exposureCount; }
    public void setExposureCount(Integer exposureCount) { this.exposureCount = exposureCount; }
    public Integer getViewCount() { return viewCount; }
    public void setViewCount(Integer viewCount) { this.viewCount = viewCount; }
    public Integer getWantCount() { return wantCount; }
    public void setWantCount(Integer wantCount) { this.wantCount = wantCount; }
    public String getDetailUrl() { return detailUrl; }
    public void setDetailUrl(String detailUrl) { this.detailUrl = detailUrl; }
    public String getDetailInfo() { return detailInfo; }
    public void setDetailInfo(String detailInfo) { this.detailInfo = detailInfo; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category; }
    public Integer getSortOrder() { return sortOrder; }
    public void setSortOrder(Integer sortOrder) { this.sortOrder = sortOrder; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
    public LocalDateTime getUpdatedTime() { return updatedTime; }
    public void setUpdatedTime(LocalDateTime updatedTime) { this.updatedTime = updatedTime; }
    public Integer getSkuCount() { return skuCount; }
    public void setSkuCount(Integer skuCount) { this.skuCount = skuCount; }
    public Integer getAutoDeliveryType() { return autoDeliveryType; }
    public void setAutoDeliveryType(Integer autoDeliveryType) { this.autoDeliveryType = autoDeliveryType; }
    public Integer getXianyuAutoDeliveryOn() { return xianyuAutoDeliveryOn; }
    public void setXianyuAutoDeliveryOn(Integer xianyuAutoDeliveryOn) { this.xianyuAutoDeliveryOn = xianyuAutoDeliveryOn; }
    public Integer getXianyuAutoReplyOn() { return xianyuAutoReplyOn; }
    public void setXianyuAutoReplyOn(Integer xianyuAutoReplyOn) { this.xianyuAutoReplyOn = xianyuAutoReplyOn; }
}
