package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.ChinaAddressDictService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 中国地址字典接口，仅提供已入库的本地数据。
 */
@RestController
@RequestMapping("/api/address-dict")
public class ChinaAddressDictController {
    private final ChinaAddressDictService addressDictService;

    public ChinaAddressDictController(ChinaAddressDictService addressDictService) {
        this.addressDictService = addressDictService;
    }

    /**
     * 返回全国省→市→区三级联动树形结构。
     * 前端一次性加载，本地做分级筛选，无需多次请求后端。
     */
    @GetMapping("/tree")
    public Result<Map<String, Object>> tree() {
        return Result.ok(addressDictService.getTree());
    }

    /** 查看同步进度 */
    @GetMapping("/stats")
    public Result<Map<String, Object>> stats() {
        return Result.ok(addressDictService.getStats());
    }
}
