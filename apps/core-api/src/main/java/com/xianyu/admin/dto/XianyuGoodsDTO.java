package com.xianyu.admin.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 闲鱼商品DTO（创建/更新）
 */
public class XianyuGoodsDTO {
    @NotNull(message = "请选择闲鱼账号")
    private Long accountId;

    @Size(max = 128, message = "外部商品ID不能超过128个字符")
    private String externalGoodsId;

    @NotBlank(message = "商品标题不能为空")
    @Size(max = 200, message = "商品标题不能超过200个字符")
    private String title;

    @Pattern(regexp = "^$|^\\d{1,8}(\\.\\d{1,2})?$", message = "价格格式不正确")
    private String price;

    @Pattern(regexp = "^$|^\\d{1,8}(\\.\\d{1,2})?$", message = "售价格式不正确")
    private String soldPrice;

    @Size(max = 2048, message = "封面图URL不能超过2048个字符")
    private String coverPic;

    @Size(max = 2048, message = "图片URL不能超过2048个字符")
    private String imageUrl;

    @Size(max = 64, message = "库存文本不能超过64个字符")
    private String stock;

    @Min(value = 0, message = "库存数量不能小于0")
    @Max(value = 999999, message = "库存数量过大")
    private Integer quantity;

    @Min(value = 0, message = "曝光次数不能小于0")
    private Integer exposureCount;

    @Min(value = 0, message = "浏览次数不能小于0")
    private Integer viewCount;

    @Min(value = 0, message = "想要人数不能小于0")
    private Integer wantCount;

    @Size(max = 2048, message = "详情页URL不能超过2048个字符")
    private String detailUrl;

    @Size(max = 10000, message = "详情描述不能超过10000个字符")
    private String detailInfo;

    @Size(max = 10000, message = "商品描述不能超过10000个字符")
    private String description;

    @Size(max = 100, message = "类目不能超过100个字符")
    private String category;

    @Min(value = 0, message = "排序值不能小于0")
    @Max(value = 999999, message = "排序值过大")
    private Integer sortOrder;

    @Min(value = 0, message = "状态值不正确")
    @Max(value = 3, message = "状态值不正确")
    private Integer status;

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getExternalGoodsId() { return externalGoodsId; }
    public void setExternalGoodsId(String externalGoodsId) { this.externalGoodsId = trimToNull(externalGoodsId); }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = trimToNull(title); }
    public String getPrice() { return price; }
    public void setPrice(String price) { this.price = trimToEmpty(price); }
    public String getSoldPrice() { return soldPrice; }
    public void setSoldPrice(String soldPrice) { this.soldPrice = trimToEmpty(soldPrice); }
    public String getCoverPic() { return coverPic; }
    public void setCoverPic(String coverPic) { this.coverPic = trimToNull(coverPic); }
    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = trimToNull(imageUrl); }
    public String getStock() { return stock; }
    public void setStock(String stock) { this.stock = trimToNull(stock); }
    public Integer getQuantity() { return quantity; }
    public void setQuantity(Integer quantity) { this.quantity = quantity; }
    public Integer getExposureCount() { return exposureCount; }
    public void setExposureCount(Integer exposureCount) { this.exposureCount = exposureCount; }
    public Integer getViewCount() { return viewCount; }
    public void setViewCount(Integer viewCount) { this.viewCount = viewCount; }
    public Integer getWantCount() { return wantCount; }
    public void setWantCount(Integer wantCount) { this.wantCount = wantCount; }
    public String getDetailUrl() { return detailUrl; }
    public void setDetailUrl(String detailUrl) { this.detailUrl = trimToNull(detailUrl); }
    public String getDetailInfo() { return detailInfo; }
    public void setDetailInfo(String detailInfo) { this.detailInfo = trimToNull(detailInfo); }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = trimToNull(description); }
    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = trimToNull(category); }
    public Integer getSortOrder() { return sortOrder; }
    public void setSortOrder(Integer sortOrder) { this.sortOrder = sortOrder; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }

    private static String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }
}
