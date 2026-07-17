-- 敏感词策略种子数据：闲鱼禁止发布的13类商品关键词
-- 来源：闲鱼商品发布规范第二章第三条
-- 场景：product（工作流商品提取过滤）
-- 动作：拦截（命中即移除商品）
-- 注意：此文件为种子数据，可安全重复执行。上线时通过 SSH 到线上服务器执行：
--   mysql -h <host> -u <user> -p <db> < seed_sensitive_words.sql
-- 执行前会先清理已有的 scene=product 种子数据，不影响用户手动添加的其他敏感词。

-- 前置清理：删除已有的 scene=product 种子数据（软删除），避免重复执行产生重复行
UPDATE admin_module_record SET deleted=1, updated_time=NOW()
WHERE module_key='sensitive-words' AND deleted=0
  AND json_extract(json_text, '$.scene') = 'product';

INSERT INTO admin_module_record (module_key, status, json_text, created_time, updated_time, deleted) VALUES

-- ========== 一、枪支弹药、危险武器、军警及行政机关用品类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '枪支', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '弹药', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '军火', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '管制刀具', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '管制器具', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '消音器', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '枪管', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '扳机', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '军警制服', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '警用器械', 'scene', 'product', 'category', '枪支弹药武器', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 二、易燃易爆、危险化学品、毒品类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '炸弹', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '火药', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '毒品', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '制毒原料', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '吸毒工具', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '烟花爆竹', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '放射性物质', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '射线装置', 'scene', 'product', 'category', '易燃易爆化学毒品', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 三、危害国家安全、破坏政治与社会稳定的有害信息类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '分裂国家', 'scene', 'product', 'category', '危害国家安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '泄露国家机密', 'scene', 'product', 'category', '危害国家安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '反动宣传', 'scene', 'product', 'category', '危害国家安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '邪教', 'scene', 'product', 'category', '危害国家安全', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 四、色情低俗、催情用品类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '色情', 'scene', 'product', 'category', '色情低俗催情', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '淫秽', 'scene', 'product', 'category', '色情低俗催情', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '催情', 'scene', 'product', 'category', '色情低俗催情', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '原味内衣', 'scene', 'product', 'category', '色情低俗催情', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 五、涉及人身隐私、安全类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '监听设备', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '窃听器', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '身份证件', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '个人隐私信息', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '盗取账号', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '破解密码', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '群发设备', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '安全带插口', 'scene', 'product', 'category', '人身隐私安全', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 六、药品、医疗器械、保健食品类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '处方药', 'scene', 'product', 'category', '药品医疗器械保健', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '美容针剂', 'scene', 'product', 'category', '药品医疗器械保健', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '农药', 'scene', 'product', 'category', '药品医疗器械保健', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '兽药', 'scene', 'product', 'category', '药品医疗器械保健', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '病原微生物', 'scene', 'product', 'category', '药品医疗器械保健', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 七、非法服务、票证、违反公序良俗类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '假章', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '假证', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '假发票', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '考试作弊', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '学术作弊', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '代体检', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '代投票', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '赌博', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '翻墙软件', 'scene', 'product', 'category', '非法服务票证', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 八、动植物、器官及捕杀工具类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '人体器官', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '保护动物', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '保护植物', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '捕杀工具', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '猫狗肉', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '鱼翅', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '熊胆', 'scene', 'product', 'category', '动植物器官捕杀', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 九、涉及盗取等非法所得及非法用途软件、工具或设备类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '偷盗工具', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '指纹膜', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '虚假定位', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '游戏外挂', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '信号屏蔽器', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '手机卡复制器', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '串号修改', 'scene', 'product', 'category', '非法所得非法工具', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 十、具有实施电信网络诈骗用途的设备、软件及服务类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '多卡宝', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', 'GoIP设备', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '猫池', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '短信猫', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '接码平台', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '改号软件', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '伪基站', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', 'IP修改软件', 'scene', 'product', 'category', '电信诈骗设备', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 十一、假冒商品、不当使用他人权利的商品或信息类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '假冒注册商标', 'scene', 'product', 'category', '假冒侵权', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '高仿', 'scene', 'product', 'category', '假冒侵权', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '精仿', 'scene', 'product', 'category', '假冒侵权', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '1:1复刻', 'scene', 'product', 'category', '假冒侵权', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 十二、未经允许违反国家行政法规或不适合交易的商品或信息类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '流通货币', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '假币', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '文物', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '烟草', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '私服', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '加款卡', 'scene', 'product', 'category', '违反行政法规', 'action', '拦截'), NOW(), NOW(), 0),

-- ========== 十三、其他违反法规或平台要求的高风险类 ==========
('sensitive-words', '正常', JSON_OBJECT('word', '传销', 'scene', 'product', 'category', '其他高风险', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '空酒瓶', 'scene', 'product', 'category', '其他高风险', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '空奶粉罐', 'scene', 'product', 'category', '其他高风险', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '品牌空瓶', 'scene', 'product', 'category', '其他高风险', 'action', '拦截'), NOW(), NOW(), 0),
('sensitive-words', '正常', JSON_OBJECT('word', '引导站外', 'scene', 'product', 'category', '其他高风险', 'action', '拦截'), NOW(), NOW(), 0);
