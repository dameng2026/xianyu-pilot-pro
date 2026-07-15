package com.xianyu.admin.service;

import org.springframework.stereotype.Service;

import java.util.Map;

@Service
public class XianyuApiProbeClient {

    public Map<String, Object> callPageHead(String cookie, String externalUid) {
        return XianyuApiUtils.callPageHead(cookie, externalUid);
    }

    public AccountAuthProbeResult probeWebSocketToken(String cookie) {
        return XianyuApiUtils.probeWebSocketToken(cookie);
    }
}
