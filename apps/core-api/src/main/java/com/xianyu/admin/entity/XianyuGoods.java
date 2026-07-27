package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

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

    /**
     * 最近30天曝光次数（来自鱼小铺数据罗盘 showPv，仅鱼小铺账号同步写入）。
     * 与 exposure_count 区分：exposure_count 为历史累计/旧来源；exposureCount30d 仅为近30天。
     */
    @Column(name = "exposure_count_30d")
    private Integer exposureCount30d;

    /**
     * 最近30天浏览次数（来自鱼小铺数据罗盘 ipv，仅鱼小铺账号同步写入）。
     * 与 view_count 区分：view_count 为历史累计/旧来源；viewCount30d 仅为近30天。
     */
    @Column(name = "view_count_30d")
    private Integer viewCount30d;

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

    /**
     * 闲鱼商品创建时间（来自鱼小铺商品管理接口 gmtCreate 字段）。
     * 与 BaseEntity.createdTime 区分：createdTime 为本地数据库记录创建时间，
     * gmtCreate 为闲鱼平台商品发布时间，仅鱼小铺账号同步时写入。
     */
    @Column(name = "gmt_create")
    private LocalDateTime gmtCreate;

    /**
     * 售整自动上架开关：1-已开启，0-已关闭。
     * 开启后当库存为 1 的商品被买走时，系统自动用完整快照数据重新发布。
     */
    @Column(name = "auto_relist_enabled")
    private Integer autoRelistEnabled = 0;

    /**
     * 重发后的新商品记录ID（指向新 xianyu_goods.id）。
     * 不为空表示该商品已重发过，避免重复触发。
     */
    @Column(name = "next_relist_goods_id")
    private Long nextRelistGoodsId;

    /**
     * 本商品是从哪个原商品重发来的（反向追溯）。
     * 用于审计与链式重发追溯。
     */
    @Column(name = "relist_source_goods_id")
    private Long relistSourceGoodsId;

    /**
     * 上次重发时间，用于审计。
     */
    @Column(name = "last_relist_at")
    private LocalDateTime lastRelistAt;

    /**
     * 是否有完整数据快照：0-无 1-有。
     * 由 Python 端写入快照时同步更新；前端展示开关时据此判断是否可开启。
     */
    @Column(name = "has_snapshot")
    private Integer hasSnapshot = 0;

    /**
     * 商品原始库存（从快照同步），用于判断 autoRelist 触发条件。
     * 仅当 originalQuantity == 1 时才会触发自动重发。
     */
    @Column(name = "original_quantity")
    private Integer originalQuantity;

    /**
     * 鱼小铺商品是否支持编辑（来自 itemExtendList.itemEdit / itemOperationInfo）。
     * 1=可编辑（默认），0=不可编辑。前端"编辑"按钮据此判断是否允许进入编辑页。
     * 普通闲鱼账号商品此字段无意义（始终为默认值 1），前端通过账号类型判断先于本字段。
     */
    @Column(name = "can_edit")
    private Integer canEdit = 1;

    /**
     * 鱼小铺商品不可编辑时的提示文案（来自 itemExtendList.itemEdit.note）。
     * 前端在 canEdit=0 时优先展示此文案。
     */
    @Column(name = "edit_note")
    private String editNote = "";

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

    public Integer getAutoReplyEnabled() { return autoReplyEnabled; }
    public void setAutoReplyEnabled(Integer autoReplyEnabled) { this.autoReplyEnabled = autoReplyEnabled; }

    public LocalDateTime getGmtCreate() { return gmtCreate; }
    public void setGmtCreate(LocalDateTime gmtCreate) { this.gmtCreate = gmtCreate; }

    public Integer getAutoRelistEnabled() { return autoRelistEnabled; }
    public void setAutoRelistEnabled(Integer autoRelistEnabled) { this.autoRelistEnabled = autoRelistEnabled; }

    public Long getNextRelistGoodsId() { return nextRelistGoodsId; }
    public void setNextRelistGoodsId(Long nextRelistGoodsId) { this.nextRelistGoodsId = nextRelistGoodsId; }

    public Long getRelistSourceGoodsId() { return relistSourceGoodsId; }
    public void setRelistSourceGoodsId(Long relistSourceGoodsId) { this.relistSourceGoodsId = relistSourceGoodsId; }

    public LocalDateTime getLastRelistAt() { return lastRelistAt; }
    public void setLastRelistAt(LocalDateTime lastRelistAt) { this.lastRelistAt = lastRelistAt; }

    public Integer getHasSnapshot() { return hasSnapshot; }
    public void setHasSnapshot(Integer hasSnapshot) { this.hasSnapshot = hasSnapshot; }

    public Integer getOriginalQuantity() { return originalQuantity; }
    public void setOriginalQuantity(Integer originalQuantity) { this.originalQuantity = originalQuantity; }

    public Integer getCanEdit() { return canEdit; }
    public void setCanEdit(Integer canEdit) { this.canEdit = canEdit; }

    public String getEditNote() { return editNote; }
    public void setEditNote(String editNote) { this.editNote = editNote; }
}
