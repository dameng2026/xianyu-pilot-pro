package com.xianyu.admin.service;

import org.springframework.stereotype.Service;

@Service
public class XianyuAccountAvailabilityProbeService {

    private final XianyuApiProbeClient probeClient;

    public XianyuAccountAvailabilityProbeService(XianyuApiProbeClient probeClient) {
        this.probeClient = probeClient;
    }

    public AccountAuthProbeResult probe(String cookie, String externalUid) {
        // 工作流预校验只关心 Cookie 登录态是否可用（page.head 能成功拿到主页资料即可）。
        // 不再额外调用 probeWebSocketToken()，原因：
        // 1. WS Token API（mtop.taobao.idlemessage.pc.login.token）需要完整的 bx-ua / bx-umidtoken / bx_et 反爬令牌，
        //    Java 直接 POST 不带这些令牌，容易被 Baxia 风控判定为异常请求返回 FAIL_SYS_USER_VALIDATE，
        //    把"调用方式缺陷"误判为"Cookie 已触发滑块验证"，导致工作流被错误拦截。
        // 2. 工作流执行（发布商品）只用 Cookie + _m_h5_tk，根本不需要 WS Token；
        //    WS Token 是 WebSocket 消息推送专用，其预检应由 Python 端 _precheck_ws_token 独立负责。
        // 3. page.head 成功即足以证明账号登录态正常，设计文档规定的探测终点也是 page.head。
        if (probeClient.callPageHead(cookie, externalUid) == null) {
            return AccountAuthProbeResult.failed("PAGE_HEAD_FAILED", "登录已失效，请重新登录闲鱼账号");
        }
        return AccountAuthProbeResult.ok();
    }

    public boolean isCookieAlive(String cookie, String externalUid) {
        return probe(cookie, externalUid).isAlive();
    }
}
