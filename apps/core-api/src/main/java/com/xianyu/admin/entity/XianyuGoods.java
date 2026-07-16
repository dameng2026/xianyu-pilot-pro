package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;

/**
 * 闲鱼商品实体
 */
@Entity
@Table(name = "xianyu_goods")
public class XianyuGoods extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "external_goods_id")
    private String externalGoodsId;

    @Column(name = "title")
    private String title;

    @Column(name = "price")
    private String price;

    @Column(name = "sold_price")
    private String soldPrice;

    @Column(name = "cover_pic")
    private String coverPic;

    @Column(name = "image_url")
    private String imageUrl;

    @Column(name = "stock")
    private String stock;

    @Column(name = "quantity")
    private Integer quantity;

    @Column(name = "exposure_count")
    private Integer exposureCount;

    @Column(name = "view_count")
    private Integer viewCount;

    @Column(name = "want_count")
    private Integer wantCount;

    @Column(name = "detail_url", columnDefinition = "TEXT")
    private String detailUrl;

    @Column(name = "detail_info", columnDefinition = "TEXT")
    private String detailInfo;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "category")
    private String category;

    @Column(name = "sort_order")
    private Integer sortOrder;

    /**
     * 商品状态（DB 约定）：1-在售/上架，0-下架/已售出/关闭；deleted=1 表示已删除
     * 注意：前端约定 0=在售、1=下架/已售出、3=已删除，Service 层做 DB↔FE 转换
     */
    @Column(name = "status")
    private Integer status;

    /**
     * 商品级自动回复开关（与 automation-service 的 auto-reply-scope 同源）。
     * 1-已开启，0-已关闭，null-未设置（继承账号级/全局）。
     */
    @Column(name = "auto_reply_enabled")
    private Integer autoReplyEnabled;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

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

    public Integer getAutoReplyEnabled() { return autoReplyEnabled; }
    public void setAutoReplyEnabled(Integer autoReplyEnabled) { this.autoReplyEnabled = autoReplyEnabled; }
}
