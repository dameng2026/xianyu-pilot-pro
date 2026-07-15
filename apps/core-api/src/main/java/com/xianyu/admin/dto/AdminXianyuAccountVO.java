package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 后台管理员专用闲鱼账号视图对象。
 * 包含跨租户查询结果，仅用于 admin-web，不返回敏感信息（encrypted_cookie、encrypted_token、password_hash 等）。
 */
public class AdminXianyuAccountVO {

    // ========== 账号基本信息 ==========
    private Long id;
    private String platform;
    private String externalUid;
    private String xianyuNickname;
    private String avatarUrl;
    private String province;
    private String city;
    private Integer accountLevel;
    private String remark;
    private Integer status;
    private LocalDateTime createdTime;
    private LocalDateTime updatedTime;

    // ========== 所属用户信息 ==========
    private Long userId;
    private String username;
    private String userNickname;
    private String userPhone;
    private String userEmail;

    // ========== 所属租户信息 ==========
    private Long tenantId;
    private String tenantName;

    // ========== 认证信息 ==========
    private String authType;
    private Integer cookieStatus;
    private LocalDateTime cookieExpiredTime;
    private LocalDateTime lastLoginTime;
    private LocalDateTime lastRefreshTime;
    private String lastErrorMessage;

    // ========== 运行时信息 ==========
    private Integer onlineStatus;
    private Integer wsStatus;
    private Double apiSuccessRate;
    private Integer avgResponseMs;
    private Integer wsLatencyMs;
    private LocalDateTime lastSyncTime;
    private LocalDateTime lastOnlineTime;
    private LocalDateTime lastHeartbeatTime;

    // ========== 会员信息 ==========
    private String membershipLevel;
    private Integer membershipStatus;
    private LocalDateTime membershipExpiredTime;

    // ========== 健康信息 ==========
    private Integer healthScore;

    // ========== getters & setters ==========

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getPlatform() { return platform; }
    public void setPlatform(String platform) { this.platform = platform; }

    public String getExternalUid() { return externalUid; }
    public void setExternalUid(String externalUid) { this.externalUid = externalUid; }

    public String getXianyuNickname() { return xianyuNickname; }
    public void setXianyuNickname(String xianyuNickname) { this.xianyuNickname = xianyuNickname; }

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

    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }

    public LocalDateTime getUpdatedTime() { return updatedTime; }
    public void setUpdatedTime(LocalDateTime updatedTime) { this.updatedTime = updatedTime; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getUserNickname() { return userNickname; }
    public void setUserNickname(String userNickname) { this.userNickname = userNickname; }

    public String getUserPhone() { return userPhone; }
    public void setUserPhone(String userPhone) { this.userPhone = userPhone; }

    public String getUserEmail() { return userEmail; }
    public void setUserEmail(String userEmail) { this.userEmail = userEmail; }

    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }

    public String getTenantName() { return tenantName; }
    public void setTenantName(String tenantName) { this.tenantName = tenantName; }

    public String getAuthType() { return authType; }
    public void setAuthType(String authType) { this.authType = authType; }

    public Integer getCookieStatus() { return cookieStatus; }
    public void setCookieStatus(Integer cookieStatus) { this.cookieStatus = cookieStatus; }

    public LocalDateTime getCookieExpiredTime() { return cookieExpiredTime; }
    public void setCookieExpiredTime(LocalDateTime cookieExpiredTime) { this.cookieExpiredTime = cookieExpiredTime; }

    public LocalDateTime getLastLoginTime() { return lastLoginTime; }
    public void setLastLoginTime(LocalDateTime lastLoginTime) { this.lastLoginTime = lastLoginTime; }

    public LocalDateTime getLastRefreshTime() { return lastRefreshTime; }
    public void setLastRefreshTime(LocalDateTime lastRefreshTime) { this.lastRefreshTime = lastRefreshTime; }

    public String getLastErrorMessage() { return lastErrorMessage; }
    public void setLastErrorMessage(String lastErrorMessage) { this.lastErrorMessage = lastErrorMessage; }

    public Integer getOnlineStatus() { return onlineStatus; }
    public void setOnlineStatus(Integer onlineStatus) { this.onlineStatus = onlineStatus; }

    public Integer getWsStatus() { return wsStatus; }
    public void setWsStatus(Integer wsStatus) { this.wsStatus = wsStatus; }

    public Double getApiSuccessRate() { return apiSuccessRate; }
    public void setApiSuccessRate(Double apiSuccessRate) { this.apiSuccessRate = apiSuccessRate; }

    public Integer getAvgResponseMs() { return avgResponseMs; }
    public void setAvgResponseMs(Integer avgResponseMs) { this.avgResponseMs = avgResponseMs; }

    public Integer getWsLatencyMs() { return wsLatencyMs; }
    public void setWsLatencyMs(Integer wsLatencyMs) { this.wsLatencyMs = wsLatencyMs; }

    public LocalDateTime getLastSyncTime() { return lastSyncTime; }
    public void setLastSyncTime(LocalDateTime lastSyncTime) { this.lastSyncTime = lastSyncTime; }

    public LocalDateTime getLastOnlineTime() { return lastOnlineTime; }
    public void setLastOnlineTime(LocalDateTime lastOnlineTime) { this.lastOnlineTime = lastOnlineTime; }

    public LocalDateTime getLastHeartbeatTime() { return lastHeartbeatTime; }
    public void setLastHeartbeatTime(LocalDateTime lastHeartbeatTime) { this.lastHeartbeatTime = lastHeartbeatTime; }

    public String getMembershipLevel() { return membershipLevel; }
    public void setMembershipLevel(String membershipLevel) { this.membershipLevel = membershipLevel; }

    public Integer getMembershipStatus() { return membershipStatus; }
    public void setMembershipStatus(Integer membershipStatus) { this.membershipStatus = membershipStatus; }

    public LocalDateTime getMembershipExpiredTime() { return membershipExpiredTime; }
    public void setMembershipExpiredTime(LocalDateTime membershipExpiredTime) { this.membershipExpiredTime = membershipExpiredTime; }

    public Integer getHealthScore() { return healthScore; }
    public void setHealthScore(Integer healthScore) { this.healthScore = healthScore; }
}