package com.xianyu.admin.dto;

public class XianyuAccountSummaryVO {

    private Long total;
    private Long normal;
    private Long verify;
    private Long wsOnline;
    private Long cookieWarn;

    public Long getTotal() { return total; }
    public void setTotal(Long total) { this.total = total; }

    public Long getNormal() { return normal; }
    public void setNormal(Long normal) { this.normal = normal; }

    public Long getVerify() { return verify; }
    public void setVerify(Long verify) { this.verify = verify; }

    public Long getWsOnline() { return wsOnline; }
    public void setWsOnline(Long wsOnline) { this.wsOnline = wsOnline; }

    public Long getCookieWarn() { return cookieWarn; }
    public void setCookieWarn(Long cookieWarn) { this.cookieWarn = cookieWarn; }
}
