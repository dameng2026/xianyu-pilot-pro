package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * 闲鱼账号认证实体
 */
@Entity
@Table(name = "xianyu_account_auth")
public class XianyuAccountAuth extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "encrypted_cookie", columnDefinition = "TEXT")
    private String encryptedCookie;

    @Column(name = "encrypted_token", columnDefinition = "TEXT")
    private String encryptedToken;

    @Column(name = "login_username")
    private String loginUsername;

    @Column(name = "encrypted_login_password", columnDefinition = "TEXT")
    private String encryptedLoginPassword;

    @Column(name = "show_browser")
    private Boolean showBrowser;

    /**
     * Cookie状态：1正常 0失效 2过期
     */
    @Column(name = "cookie_status")
    private Integer cookieStatus;

    @Column(name = "ws_token")
    private String wsToken;

    @Column(name = "token_expire_time")
    private LocalDateTime tokenExpireTime;

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

    public String getEncryptedCookie() {
        return encryptedCookie;
    }

    public void setEncryptedCookie(String encryptedCookie) {
        this.encryptedCookie = encryptedCookie;
    }

    public String getEncryptedToken() {
        return encryptedToken;
    }

    public void setEncryptedToken(String encryptedToken) {
        this.encryptedToken = encryptedToken;
    }

    public String getLoginUsername() {
        return loginUsername;
    }

    public void setLoginUsername(String loginUsername) {
        this.loginUsername = loginUsername;
    }

    public String getEncryptedLoginPassword() {
        return encryptedLoginPassword;
    }

    public void setEncryptedLoginPassword(String encryptedLoginPassword) {
        this.encryptedLoginPassword = encryptedLoginPassword;
    }

    public Boolean getShowBrowser() {
        return showBrowser;
    }

    public void setShowBrowser(Boolean showBrowser) {
        this.showBrowser = showBrowser;
    }

    public Integer getCookieStatus() {
        return cookieStatus;
    }

    public void setCookieStatus(Integer cookieStatus) {
        this.cookieStatus = cookieStatus;
    }

    public String getWsToken() {
        return wsToken;
    }

    public void setWsToken(String wsToken) {
        this.wsToken = wsToken;
    }

    public LocalDateTime getTokenExpireTime() {
        return tokenExpireTime;
    }

    public void setTokenExpireTime(LocalDateTime tokenExpireTime) {
        this.tokenExpireTime = tokenExpireTime;
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
