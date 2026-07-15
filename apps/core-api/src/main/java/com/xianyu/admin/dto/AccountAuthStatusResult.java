package com.xianyu.admin.dto;

import java.time.LocalDateTime;

public class AccountAuthStatusResult {
    private boolean usable;
    private Integer cookieStatus;
    private String loginStatusCode;
    private String loginStatusMessage;
    private LocalDateTime checkedAt;
    private String source;

    public boolean isUsable() {
        return usable;
    }

    public void setUsable(boolean usable) {
        this.usable = usable;
    }

    public Integer getCookieStatus() {
        return cookieStatus;
    }

    public void setCookieStatus(Integer cookieStatus) {
        this.cookieStatus = cookieStatus;
    }

    public String getLoginStatusCode() {
        return loginStatusCode;
    }

    public void setLoginStatusCode(String loginStatusCode) {
        this.loginStatusCode = loginStatusCode;
    }

    public String getLoginStatusMessage() {
        return loginStatusMessage;
    }

    public void setLoginStatusMessage(String loginStatusMessage) {
        this.loginStatusMessage = loginStatusMessage;
    }

    public LocalDateTime getCheckedAt() {
        return checkedAt;
    }

    public void setCheckedAt(LocalDateTime checkedAt) {
        this.checkedAt = checkedAt;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }
}
