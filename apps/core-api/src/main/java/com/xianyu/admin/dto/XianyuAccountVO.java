package com.xianyu.admin.dto;

import java.time.LocalDateTime;

public class XianyuAccountVO {

    private Long id;
    private String externalUid;
    private String nickname;
    private String avatarUrl;
    private String province;
    private String city;
    private Integer accountLevel;
    private String remark;
    private Integer status;
    private String membershipLevel;
    private LocalDateTime membershipExpiredTime;
    private Integer cookieStatus;
    private Boolean authUsable;
    private String loginStatusCode;
    private String loginStatusMessage;
    private LocalDateTime loginCheckTime;
    private String loginStatusSource;
    private Integer wsStatus;
    private Integer onlineStatus;
    private LocalDateTime lastSyncTime;
    private LocalDateTime lastOnlineTime;
    private Double apiSuccessRate;
    private Integer avgResponseMs;
    private Integer wsLatencyMs;
    private Integer healthScore;

    // ===== 刷新资料字段（来自闲鱼 user.page.head / user.page.nav） =====
    private String displayName;
    private String ipLocation;
    private String introduction;
    private Integer followers;
    private Integer following;
    private String sellerLevel;
    private Integer fishShopScore;
    private Boolean fishShopUser;
    private String praiseRatio;
    private Integer reviewNum;
    private Integer soldCount;
    private LocalDateTime profileRefreshTime;
    private Integer messageExpireTime;
    private Boolean scheduledRedelivery;
    private Boolean autoPolish;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getExternalUid() { return externalUid; }
    public void setExternalUid(String externalUid) { this.externalUid = externalUid; }

    public String getNickname() { return nickname; }
    public void setNickname(String nickname) { this.nickname = nickname; }

    public String getAvatarUrl() { return avatarUrl; }
    public void setAvatarUrl(String avatarUrl) { this.avatarUrl = avatarUrl; }

    public String getProvince() { return province; }
    public void setProvince(String province) { this.province = province; }

    public String getCity() { return city; }
    public void setCity(String city) { this.city = city; }

    public Integer getAccountLevel() { return accountLevel; }
    public void setAccountLevel(Integer accountLevel) { this.accountLevel = accountLevel; }

    public String getRemark() { return remark; }
    public void setRemark(String remark) { this.remark = remark; }

    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }

    public String getMembershipLevel() { return membershipLevel; }
    public void setMembershipLevel(String membershipLevel) { this.membershipLevel = membershipLevel; }

    public LocalDateTime getMembershipExpiredTime() { return membershipExpiredTime; }
    public void setMembershipExpiredTime(LocalDateTime membershipExpiredTime) { this.membershipExpiredTime = membershipExpiredTime; }

    public Integer getCookieStatus() { return cookieStatus; }
    public void setCookieStatus(Integer cookieStatus) { this.cookieStatus = cookieStatus; }

    public Boolean getAuthUsable() { return authUsable; }
    public void setAuthUsable(Boolean authUsable) { this.authUsable = authUsable; }

    public String getLoginStatusCode() { return loginStatusCode; }
    public void setLoginStatusCode(String loginStatusCode) { this.loginStatusCode = loginStatusCode; }

    public String getLoginStatusMessage() { return loginStatusMessage; }
    public void setLoginStatusMessage(String loginStatusMessage) { this.loginStatusMessage = loginStatusMessage; }

    public LocalDateTime getLoginCheckTime() { return loginCheckTime; }
    public void setLoginCheckTime(LocalDateTime loginCheckTime) { this.loginCheckTime = loginCheckTime; }

    public String getLoginStatusSource() { return loginStatusSource; }
    public void setLoginStatusSource(String loginStatusSource) { this.loginStatusSource = loginStatusSource; }

    public Integer getWsStatus() { return wsStatus; }
    public void setWsStatus(Integer wsStatus) { this.wsStatus = wsStatus; }

    public Integer getOnlineStatus() { return onlineStatus; }
    public void setOnlineStatus(Integer onlineStatus) { this.onlineStatus = onlineStatus; }

    public LocalDateTime getLastSyncTime() { return lastSyncTime; }
    public void setLastSyncTime(LocalDateTime lastSyncTime) { this.lastSyncTime = lastSyncTime; }

    public LocalDateTime getLastOnlineTime() { return lastOnlineTime; }
    public void setLastOnlineTime(LocalDateTime lastOnlineTime) { this.lastOnlineTime = lastOnlineTime; }

    public Double getApiSuccessRate() { return apiSuccessRate; }
    public void setApiSuccessRate(Double apiSuccessRate) { this.apiSuccessRate = apiSuccessRate; }

    public Integer getAvgResponseMs() { return avgResponseMs; }
    public void setAvgResponseMs(Integer avgResponseMs) { this.avgResponseMs = avgResponseMs; }

    public Integer getWsLatencyMs() { return wsLatencyMs; }
    public void setWsLatencyMs(Integer wsLatencyMs) { this.wsLatencyMs = wsLatencyMs; }

    public Integer getHealthScore() { return healthScore; }
    public void setHealthScore(Integer healthScore) { this.healthScore = healthScore; }

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

    public LocalDateTime getProfileRefreshTime() { return profileRefreshTime; }
    public void setProfileRefreshTime(LocalDateTime profileRefreshTime) { this.profileRefreshTime = profileRefreshTime; }

    public Integer getMessageExpireTime() { return messageExpireTime; }
    public void setMessageExpireTime(Integer messageExpireTime) { this.messageExpireTime = messageExpireTime; }

    public Boolean getScheduledRedelivery() { return scheduledRedelivery; }
    public void setScheduledRedelivery(Boolean scheduledRedelivery) { this.scheduledRedelivery = scheduledRedelivery; }

    public Boolean getAutoPolish() { return autoPolish; }
    public void setAutoPolish(Boolean autoPolish) { this.autoPolish = autoPolish; }
}
