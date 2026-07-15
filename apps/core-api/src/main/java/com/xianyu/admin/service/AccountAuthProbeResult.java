package com.xianyu.admin.service;

public class AccountAuthProbeResult {
    private final boolean alive;
    private final String code;
    private final String message;

    private AccountAuthProbeResult(boolean alive, String code, String message) {
        this.alive = alive;
        this.code = code;
        this.message = message;
    }

    public static AccountAuthProbeResult ok() {
        return new AccountAuthProbeResult(true, "OK", "账号登录状态正常");
    }

    public static AccountAuthProbeResult failed(String code, String message) {
        return new AccountAuthProbeResult(false, code, message);
    }

    public boolean isAlive() {
        return alive;
    }

    public String getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
