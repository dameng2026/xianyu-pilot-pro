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
    /**
     * 最近30天曝光次数（鱼小铺数据罗盘 showPv，仅鱼小铺账号同步写入）。
     * 前端商品详情侧边栏"曝光"位置优先展示此字段。
     */
    private Integer exposureCount30d;
    /**
     * 最近30天浏览次数（鱼小铺数据罗盘 ipv，仅鱼小铺账号同步写入）。
     * 前端商品详情侧边栏"浏览"位置优先展示此字段。
     */
    private Integer viewCount30d;
    private String detailUrl;
    private String detailInfo;
    private String description;
    private String category;
    private Integer sortOrder;
    private Integer status;
    private LocalDateTime createdTime;
    /**
     * 闲鱼商品创建时间（鱼小铺商品管理接口 gmtCreate 字段）。
     * 与 createdTime 区分：createdTime 为本地数据库记录创建时间。
     */
    private LocalDateTime gmtCreate;
    private LocalDateTime updatedTime;
    private Integer skuCount;
    private Integer autoDeliveryType;
    private Integer xianyuAutoDeliveryOn;
    private Integer xianyuAutoReplyOn;
    /**
     * 售整自动上架开关：1-已开启，0-已关闭。
     */
    private Integer autoRelistEnabled;
    /**
     * 是否有完整数据快照：0-无 1-有。
     * 前端据此判断是否允许开启开关。
     */
    private Integer hasSnapshot;
    /**
     * 商品原始库存（从快照同步），用于判断 autoRelist 触发条件。
     */
    private Integer originalQuantity;
    /**
     * 重发后的新商品记录ID。不为空表示已重发过。
     */
    private Long nextRelistGoodsId;
    /**
     * 鱼小铺商品是否支持编辑：1=可编辑（默认），0=不可编辑。
     * 普通闲鱼账号商品此字段无意义，前端通过账号类型先于本字段判断。
     */
    private Integer canEdit;
    /**
     * 鱼小铺商品不可编辑时的提示文案（来自闲鱼 itemExtendList.itemEdit.note）。
     */
    private String editNote;

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
    public Integer getExposureCount30d() { return exposureCount30d; }
    public void setExposureCount30d(Integer exposureCount30d) { this.exposureCount30d = exposureCount30d; }
    public Integer getViewCount30d() { return viewCount30d; }
    public void setViewCount30d(Integer viewCount30d) { this.viewCount30d = viewCount30d; }
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
    public LocalDateTime getGmtCreate() { return gmtCreate; }
    public void setGmtCreate(LocalDateTime gmtCreate) { this.gmtCreate = gmtCreate; }
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
    public Integer getAutoRelistEnabled() { return autoRelistEnabled; }
    public void setAutoRelistEnabled(Integer autoRelistEnabled) { this.autoRelistEnabled = autoRelistEnabled; }
    public Integer getHasSnapshot() { return hasSnapshot; }
    public void setHasSnapshot(Integer hasSnapshot) { this.hasSnapshot = hasSnapshot; }
    public Integer getOriginalQuantity() { return originalQuantity; }
    public void setOriginalQuantity(Integer originalQuantity) { this.originalQuantity = originalQuantity; }
    public Long getNextRelistGoodsId() { return nextRelistGoodsId; }
    public void setNextRelistGoodsId(Long nextRelistGoodsId) { this.nextRelistGoodsId = nextRelistGoodsId; }
    public Integer getCanEdit() { return canEdit; }
    public void setCanEdit(Integer canEdit) { this.canEdit = canEdit; }
    public String getEditNote() { return editNote; }
    public void setEditNote(String editNote) { this.editNote = editNote; }
}
