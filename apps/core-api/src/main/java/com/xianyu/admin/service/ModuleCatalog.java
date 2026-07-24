package com.xianyu.admin.service;

import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ModuleCatalog {
    private final Map<String, ModuleMeta> metas = new LinkedHashMap<>();

    public ModuleCatalog() {
        add("users", "用户管理", "管理平台注册用户信息，包括用户ID、用户账户、手机号、邮箱、用户等级及状态", cols("userId:用户ID:90", "account:用户账户:150", "phone:手机号:130", "email:邮箱:180", "userLevelName:用户等级:110:tag", "status:状态:100:tag", "lastLoginTime:最近登录:170", "createdTime:创建时间:170"));
        add("plans", "套餐管理", "配置与用户前台 VIP 会员中心共用的套餐权益、价格、周期与上下架", cols("id:ID:80", "planName:套餐名称:160", "planCode:套餐编码:120", "priceMonth:月价:100", "priceQuarter:季价:100", "priceYear:年价:100", "featuresText:套餐介绍:320:textarea", "status:状态:100:tag"));
        add("licenses", "授权码管理", "生成授权码、兑换记录和禁用", cols("id:ID:80", "code:授权码:220", "planName:套餐:120", "durationDays:天数:90", "status:状态:100:tag", "usedBy:使用用户:140", "usedTime:使用时间:170"));
        add("model-config-general", "通用模型配置", "配置平台默认模型、Base URL 与 API Key", cols("id:ID:80", "providerName:提供商名称:180", "baseUrl:Base URL:260", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("model-config-chat", "对话模型配置", "对话模型名称、参数及连接信息", cols("id:ID:80", "modelName:模型名称:180", "baseUrl:Base URL:260", "maxTokens:最大Token:110", "temperature:温度:100", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("model-config-image", "生图模型配置", "图像生成模型的参数与连接信息", cols("id:ID:80", "modelName:模型名称:180", "baseUrl:Base URL:260", "imageSize:图片尺寸:120", "quality:质量:100", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("model-config-image-2", "生图模型2配置", "第二个图像生成模型的参数与连接信息",
            cols("id:ID:80", "modelName:模型名称:180", "baseUrl:Base URL:260", "imageSize:图片尺寸:120", "quality:质量:100", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("model-config-image-3", "生图模型3配置", "第三个图像生成模型的参数与连接信息",
            cols("id:ID:80", "modelName:模型名称:180", "baseUrl:Base URL:260", "imageSize:图片尺寸:120", "quality:质量:100", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("model-config-image-prompts", "生图类目提示词", "按商品类目维护闲鱼主图提示词模板与匹配关键词", cols(
                "id:ID:80",
                "name:类目名称:150",
                "categoryKey:类目标识:140",
                "enabled:启用:90:bool",
                "sortOrder:排序:90",
                "matchKeywords:匹配关键词:240",
                "promptTemplate:提示词模板:360",
                "status:状态:100:tag",
                "updatedTime:更新时间:170"
        ));
        add("notify-channels", "通知渠道", "邮件、Webhook、飞书、企业微信配置", cols("id:ID:80", "channelName:渠道名称:160", "channelType:类型:120:tag", "target:目标:220", "status:状态:100:tag", "updatedTime:更新时间:170"));
        add("notify-logs", "通知日志", "消息通知、告警通知和套餐到期通知记录", cols("id:ID:80", "channelName:渠道:140", "title:标题:200", "receiver:接收人:150", "sendStatus:状态:100:tag", "createdTime:发送时间:170"));
        add("risk-events", "风控事件", "账号、任务、登录、AI 等风险事件处理", cols("id:ID:80", "eventType:事件类型:150", "riskLevel:等级:100:tag", "username:用户:120", "accountName:账号:140", "title:标题:220", "status:状态:100:tag", "createdTime:发生时间:170"));
        add("system-settings", "系统配置", "全局配置、密钥、存储、邮件、地图、开关", cols("id:ID:80", "settingKey:配置键:180", "settingValue:配置值:260", "settingGroup:分组:120", "isSecret:敏感:90:tag", "updatedTime:更新时间:170"));
        add("runtime", "运行日志", "节点状态、运行日志、内存、磁盘和线程池", cols("id:ID:80", "nodeName:节点:140", "nodeIp:IP:130", "cpuUsage:CPU:90", "memoryUsage:内存:90", "diskUsage:磁盘:90", "status:状态:100:tag", "lastHeartbeatTime:心跳:170"));
        add("backups", "数据备份", "MySQL 备份、恢复、下载和保留策略", cols("id:ID:80", "backupName:备份名称:180", "backupType:类型:110:tag", "fileSize:大小:90", "status:状态:100:tag", "createdTime:创建时间:170"));
        add("versions", "版本管理", "系统版本、升级记录和灰度发布", cols("id:ID:80", "version:版本号:120", "title:标题:200", "releaseType:类型:100:tag", "status:状态:100:tag", "releasedTime:发布时间:170"));

        add("xianyu-accounts", "闲鱼账号", "管理平台内所有普通用户绑定的闲鱼账号，包括账号状态、Cookie/WebSocket/在线状态、会员等级等", cols(
                "id:ID:80",
                "externalUid:闲鱼UID:140",
                "xianyuNickname:闲鱼昵称:140",
                "username:所属用户:130",
                "status:账号状态:100:tag",
                "cookieStatus:Cookie状态:120:tag",
                "wsStatus:WebSocket:110:tag",
                "onlineStatus:在线状态:100:tag",
                "membershipLevel:会员等级:110:tag",
                "lastLoginTime:最后登录:170",
                "lastSyncTime:最后同步:170",
                "createdTime:创建时间:170"
        ));

        add("goods", "商品监管", "高转化虚拟商品模板和交易数据", cols("id:ID:80", "goodsTitle:商品标题:280", "username:所属用户:130", "price:价格:100", "autoDelivery:自动发货:100:tag", "autoReply:自动回复:100:tag", "status:状态:100:tag", "createdTime:创建时间:170"));
        add("orders", "订单监管", "闲鱼订单数据与状态追踪", cols("id:ID:80", "orderNo:订单号:200", "buyerName:买家:130", "username:所属用户:130", "amount:金额:100", "payStatus:支付:100:tag", "orderStatus:订单状态:110:tag", "deliveryStatus:发货状态:110:tag", "createdTime:创建时间:170"));
        add("messages", "消息监管", "闲鱼聊天消息记录和合规审查", cols("id:ID:80", "buyerName:买家:130", "accountName:账号:140", "messageType:类型:100:tag", "replyType:回复:100:tag", "summary:摘要:240", "createdTime:创建时间:170"));
        add("delivery", "自动发货监管", "卡密发放与自动发货状态", cols("id:ID:80", "accountName:账号:140", "deliveryType:发货类型:100:tag", "orderStatus:状态:100:tag", "retryCount:重试:80", "failReason:失败原因:200", "createdTime:创建时间:170"));
        add("auto-reply", "自动回复监管", "自动回复规则、命中统计和效果分析", cols("id:ID:80", "ruleName:规则名称:180", "accountName:账号:130", "replyMode:回复模式:100:tag", "hitCount:命中次数:100", "status:状态:100:tag", "createdTime:创建时间:170"));
        add("kami", "卡密监管", "预生成卡密列表、库存和使用记录", cols("id:ID:80", "configName:配置名称:170", "accountName:账号:130", "totalCount:总数:90", "usedCount:已用:90", "remainCount:剩余:90", "status:状态:100:tag", "createdTime:创建时间:170"));
        add("ai-usage", "AI 调用日志", "真实 AI 调用 usage、人民币成本、Token 扣费和余额变动", cols("id:ID:80", "providerName:提供商:150", "modelName:模型:180", "username:用户:130", "scene:场景:120:tag", "promptTokens:输入Token:110", "completionTokens:输出Token:110", "chargeTokens:扣费Token:120", "cost:费用:90", "statusText:状态:90:tag", "createdTime:时间:170"));
        add("ai-token", "Token 流水", "按用户展示充值、AI 扣费等余额变动流水", cols("id:ID:80", "username:用户:140", "changeType:类型:110:tag", "changeAmount:变动Token:120", "beforeBalance:变动前:110", "afterBalance:变动后:110", "refNo:关联单号:170", "remark:备注:180", "createdTime:时间:170"));
        add("rag", "RAG 知识库", "RAG 文档上传和向量化管理", cols("id:ID:80", "knowledgeName:知识库名:180", "docCount:文档数:90", "vectorCount:向量数:90", "storageSize:存储大小:100", "status:状态:100:tag", "createdTime:创建时间:170"));
        add("sensitive-words", "敏感词策略", "AI 润色文案与工作流商品提取的敏感词拦截策略；命中即拦截/移除，避免账号封禁", cols(
                "id:ID:80",
                "word:敏感词:200",
                "scene:应用场景:140:tag",
                "category:分类:140",
                "action:动作:90:tag",
                "status:状态:100:tag",
                "createdTime:创建时间:170"
        ));

        add("hot-goods", "数据统计", "热销商品统计，筛选当日销量大于5件的商品数据，用于模型训练和爆款文案分析", cols(
                "id:ID:80",
                "goodsTitle:商品标题:280",
                "price:价格:100",
                "coverPic:封面图:120:image",
                "dailySales:当日销量:100",
                "statDate:统计日期:120",
                "accountName:所属账号:140",
                "createdTime:统计时间:170"
        ));
        add("alerts", "异常告警", "系统异常告警事件聚合，包含任务失败、登录异常、AI 调用失败等告警", cols(
                "id:ID:80",
                "alertType:告警类型:140:tag",
                "level:级别:100:tag",
                "source:来源:140",
                "title:标题:240",
                "username:关联用户:130",
                "status:状态:100:tag",
                "createdTime:发生时间:170"
        ));
        add("files", "文件管理", "上传文件、LOGO、附件等资源文件清单与大小统计", cols(
                "id:ID:80",
                "fileName:文件名:240",
                "filePath:存储路径:280",
                "fileSize:大小:100",
                "fileType:类型:100:tag",
                "username:上传用户:130",
                "createdTime:上传时间:170"
        ));
    }

    private void add(String key, String title, String desc, List<Map<String, Object>> columns) {
        metas.put(key, new ModuleMeta(key, title, desc, columns));
    }

    private List<Map<String, Object>> cols(String... specs) {
        List<Map<String, Object>> list = new ArrayList<>();
        for (String spec : specs) {
            String[] arr = spec.split(":");
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("prop", arr[0]);
            m.put("label", arr[1]);
            m.put("width", arr.length > 2 ? Integer.parseInt(arr[2]) : 120);
            if (arr.length > 3) m.put("type", arr[3]);
            list.add(m);
        }
        return list;
    }

    public ModuleMeta get(String key) {
        ModuleMeta meta = metas.get(key);
        if (meta == null) {
            throw new IllegalArgumentException("未知的模块: " + key);
        }
        return meta;
    }
    public Collection<ModuleMeta> all() { return metas.values(); }

    public record ModuleMeta(String key, String title, String description, List<Map<String, Object>> columns) {}
}
