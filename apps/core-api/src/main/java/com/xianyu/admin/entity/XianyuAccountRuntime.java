package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 闲鱼账号运行时状态实体
 */
@Entity
@Table(name = "xianyu_account_runtime")
public class XianyuAccountRuntime extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    /**
     * 在线状态：1在线 0离线
     */
    @Column(name = "online_status")
    private Integer onlineStatus;

    /**
     * WebSocket状态：1在线 0离线
     */
    @Column(name = "ws_status")
    private Integer wsStatus;

    @Column(name = "ws_latency_ms")
    private Integer wsLatencyMs;

    @Column(name = "cookie_status")
    private Integer cookieStatus;

    @Column(name = "last_login_time")
    private LocalDateTime lastLoginTime;

    @Column(name = "last_heartbeat_time")
    private LocalDateTime lastHeartbeatTime;

    @Column(name = "last_online_time")
    private LocalDateTime lastOnlineTime;

    @Column(name = "last_sync_time")
    private LocalDateTime lastSyncTime;

    @Column(name = "last_login_status_code")
    private String lastLoginStatusCode;

    @Column(name = "last_login_status_message")
    private String lastLoginStatusMessage;

    @Column(name = "last_login_check_time")
    private LocalDateTime lastLoginCheckTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getAccountId() {
        return accountId;
    }

    public void setAccountId(Long accountId) {
        this.accountId = accountId;
    }

    public Integer getOnlineStatus() {
        return onlineStatus;
    }

    public void setOnlineStatus(Integer onlineStatus) {
        this.onlineStatus = onlineStatus;
    }

    public Integer getWsStatus() {
        return wsStatus;
    }

    public void setWsStatus(Integer wsStatus) {
        this.wsStatus = wsStatus;
    }

    public Integer getWsLatencyMs() {
        return wsLatencyMs;
    }

    public void setWsLatencyMs(Integer wsLatencyMs) {
        this.wsLatencyMs = wsLatencyMs;
    }

    public Integer getCookieStatus() {
        return cookieStatus;
    }

    public void setCookieStatus(Integer cookieStatus) {
        this.cookieStatus = cookieStatus;
    }

    public LocalDateTime getLastLoginTime() {
        return lastLoginTime;
    }

    public void setLastLoginTime(LocalDateTime lastLoginTime) {
        this.lastLoginTime = lastLoginTime;
    }

    public LocalDateTime getLastHeartbeatTime() {
        return lastHeartbeatTime;
    }

    public void setLastHeartbeatTime(LocalDateTime lastHeartbeatTime) {
        this.lastHeartbeatTime = lastHeartbeatTime;
    }

    public LocalDateTime getLastOnlineTime() {
        return lastOnlineTime;
    }

    public void setLastOnlineTime(LocalDateTime lastOnlineTime) {
        this.lastOnlineTime = lastOnlineTime;
    }

    public LocalDateTime getLastSyncTime() {
        return lastSyncTime;
    }

    public void setLastSyncTime(LocalDateTime lastSyncTime) {
        this.lastSyncTime = lastSyncTime;
    }

    public String getLastLoginStatusCode() {
        return lastLoginStatusCode;
    }

    public void setLastLoginStatusCode(String lastLoginStatusCode) {
        this.lastLoginStatusCode = lastLoginStatusCode;
    }

    public String getLastLoginStatusMessage() {
        return lastLoginStatusMessage;
    }

    public void setLastLoginStatusMessage(String lastLoginStatusMessage) {
        this.lastLoginStatusMessage = lastLoginStatusMessage;
    }

    public LocalDateTime getLastLoginCheckTime() {
        return lastLoginCheckTime;
    }

    public void setLastLoginCheckTime(LocalDateTime lastLoginCheckTime) {
        this.lastLoginCheckTime = lastLoginCheckTime;
    }
}
