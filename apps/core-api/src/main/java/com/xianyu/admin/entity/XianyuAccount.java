package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 闲鱼账号实体
 */
@Entity
@Table(name = "xianyu_account")
public class XianyuAccount extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "external_uid", unique = true)
    private String externalUid;

    @Column(name = "nickname")
    private String nickname;

    @Column(name = "avatar_url")
    private String avatarUrl;

    @Column(name = "province")
    private String province;

    @Column(name = "city")
    private String city;

    @Column(name = "account_level")
    private Integer accountLevel;

    @Column(name = "remark")
    private String remark;

    /**
     * 状态：1正常 0禁用
     */
    @Column(name = "status")
    private Integer status;

    // ===== 刷新资料字段（来自闲鱼 user.page.head / user.page.nav） =====

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "ip_location")
    private String ipLocation;

    @Column(name = "introduction", columnDefinition = "TEXT")
    private String introduction;

    @Column(name = "followers")
    private Integer followers;

    @Column(name = "following")
    private Integer following;

    @Column(name = "seller_level")
    private String sellerLevel;

    @Column(name = "fish_shop_score")
    private Integer fishShopScore;

    @Column(name = "fish_shop_user")
    private Boolean fishShopUser;

    @Column(name = "praise_ratio")
    private String praiseRatio;

    @Column(name = "review_num")
    private Integer reviewNum;

    @Column(name = "sold_count")
    private Integer soldCount;

    @Column(name = "message_expire_time")
    private Integer messageExpireTime;

    @Column(name = "scheduled_redelivery")
    private Boolean scheduledRedelivery;

    @Column(name = "auto_polish")
    private Boolean autoPolish;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public String getExternalUid() {
        return externalUid;
    }

    public void setExternalUid(String externalUid) {
        this.externalUid = externalUid;
    }

    public String getNickname() {
        return nickname;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }

    public String getAvatarUrl() {
        return avatarUrl;
    }

    public void setAvatarUrl(String avatarUrl) {
        this.avatarUrl = avatarUrl;
    }

    public String getProvince() {
        return province;
    }

    public void setProvince(String province) {
        this.province = province;
    }

    public String getCity() {
        return city;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public Integer getAccountLevel() {
        return accountLevel;
    }

    public void setAccountLevel(Integer accountLevel) {
        this.accountLevel = accountLevel;
    }

    public String getRemark() {
        return remark;
    }

    public void setRemark(String remark) {
        this.remark = remark;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }

    public String getIpLocation() { return ipLocation; }
    public void setIpLocation(String ipLocation) { this.ipLocation = ipLocation; }

    public String getIntroduction() { return introduction; }
    public void setIntroduction(String introduction) { this.introduction = introduction; }

    public Integer getFollowers() { return followers; }
    public void setFollowers(Integer followers) { this.followers = followers; }

    public Integer getFollowing() { return following; }
    public void setFollowing(Integer following) { this.following = following; }

    public String getSellerLevel() { return sellerLevel; }
    public void setSellerLevel(String sellerLevel) { this.sellerLevel = sellerLevel; }

    public Integer getFishShopScore() { return fishShopScore; }
    public void setFishShopScore(Integer fishShopScore) { this.fishShopScore = fishShopScore; }

    public Boolean getFishShopUser() { return fishShopUser; }
    public void setFishShopUser(Boolean fishShopUser) { this.fishShopUser = fishShopUser; }

    public String getPraiseRatio() { return praiseRatio; }
    public void setPraiseRatio(String praiseRatio) { this.praiseRatio = praiseRatio; }

    public Integer getReviewNum() { return reviewNum; }
    public void setReviewNum(Integer reviewNum) { this.reviewNum = reviewNum; }

    public Integer getSoldCount() { return soldCount; }
    public void setSoldCount(Integer soldCount) { this.soldCount = soldCount; }

    public Integer getMessageExpireTime() { return messageExpireTime; }
    public void setMessageExpireTime(Integer messageExpireTime) { this.messageExpireTime = messageExpireTime; }

    public Boolean getScheduledRedelivery() { return scheduledRedelivery; }
    public void setScheduledRedelivery(Boolean scheduledRedelivery) { this.scheduledRedelivery = scheduledRedelivery; }

    public Boolean getAutoPolish() { return autoPolish; }
    public void setAutoPolish(Boolean autoPolish) { this.autoPolish = autoPolish; }
}
