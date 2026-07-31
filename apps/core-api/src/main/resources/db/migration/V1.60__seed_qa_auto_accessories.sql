-- ============================================================
-- V1.60: 汽车用品 AI 客服学习知识库种子数据
-- 一级分类: 汽车用品 (auto_accessories)
-- 二级分类: auto_decor / auto_parts / auto_electronics / auto_motorcycle / auto_bicycle
-- 规模: 5 个二级分类 × 30 条 = 150 条高价值 Q&A
-- 风格: 闲鱼真实买家刁钻提问 + 销冠级化解话术, 突出车型适配与正品保障
-- 场景覆盖: 车型适配/是否原装/安装方式/是否含安装/保修/新旧程度/性能参数/兼容性
-- 幂等说明: content_hash = MD5(question + answer), 重复执行会因唯一键冲突跳过
--          (如需可重复执行, 可在外层包 NOT EXISTS 或 INSERT IGNORE)
-- learn_batch_id: seed-v1.60
-- source_type: seed
-- ============================================================

-- ============ 1. 汽车装饰 auto_decor (30 条) ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.60', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'auto_decor' AS code, '这款脚垫适合我的丰田卡罗拉吗?买的时候要备注什么?' AS question, '亲,这款全包围脚垫是专车专用版,支持丰田卡罗拉2014到2023款全系车型。下单时麻烦备注一下年款和排量,我帮您核对车型库确保无误。我们用的是TPE环保材质无异味,原车卡扣无损安装不动螺丝,5分钟即可完成。脚垫包边走线整齐耐磨损易清洗,质保三年,性价比比4S店高很多,放心拍。' AS answer, '脚垫,车型适配,卡罗拉,TPE,质保' AS tags, '丰田卡罗拉脚垫车型适配话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_decor', '座套是真皮的吗?新车刚装会不会有刺鼻味道?', '亲,这款座套采用优质PU环保皮革加高密度海绵内衬,手感和真皮接近但更耐脏易打理。新座套刚打开会有轻微皮革味,通风晾1到2天就散了,不是甲醛那种刺鼻味。我们是源头工厂直发,做工走线整齐包边不翘边,前排后排全套适配,质保两年。建议深色内饰选黑色或灰色,耐脏显档次。' AS answer, '座套,PU皮,异味,环保,质保' AS tags, '座套材质与异味化解话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_decor', '香水座放中控台会不会漏液损坏面板?哪种香味好闻?', '亲放心,这款固体香膏款不会漏液,放中控台或杯架都安全。液体款用防漏阀芯设计倒置也不漏。香味有古龙、海洋、檀香、白茶等6种可选,留香2到3个月可重复添加。男士推荐檀香沉稳大气,女士推荐白茶清新不甜腻。建议夏天选固体款更稳妥,冬天液体款散香更好。' AS answer, '香水,漏液,固体香膏,香型,留香' AS tags, '香水防漏与香型推荐话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_decor', '方向盘套我的大众朗逸能用吗?安装会不会很难?', '亲,通用款方向盘套适配37到38cm标准方向盘,覆盖95%车型,大众朗逸完全没问题。M码适合轿车,L码适合SUV。安装时套入后用手掌沿边缘推一圈即可,内置防滑硅胶颗粒不移位不滑脱。建议拍下时备注车型,我帮您确认尺寸避免装不上。真皮款手感细腻防滑,长期使用不变形。' AS answer, '方向盘套,朗逸,尺寸,安装,防滑' AS tags, '方向盘套车型适配话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_decor', '挂件挂在后视镜上会不会挡视线?安全气囊弹出有影响吗?', '亲,这款挂件长度8cm,挂在后视镜下方不会挡视线,也不会影响副驾安全气囊弹出。建议挂件底部距中控台保留15cm以上距离。我们用的是天然檀木加纯铜配件,重量轻不晃动开车无异响。也可以选水晶款寓意平安吉祥,自用送人都合适。挂绳可调节长度,方便您调整最佳位置。' AS answer, '挂件,挡视线,安全气囊,檀木,挂绳' AS tags, '挂件安全与视线化解话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_decor', '车身贴纸撕下来会不会留胶?伤不伤车漆?', '亲,这款用的是户外级可移胶,正常撕下不留胶不伤漆,质保3年不褪色不起边。撕的时候建议用电吹风加热一下更轻松。避免新车3个月内贴,刚喷漆的车建议等1个月再贴。贴之前车身要清洁干净擦干,温度10度以上施工效果最佳。我们有多种图案可选,支持定制LOGO,起订量10张。' AS answer, '贴纸,留胶,车漆,可移胶,定制' AS tags, '贴纸不留胶与车漆保护话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_decor', '全包围脚垫有异味吗?家里有孕妇小孩能用吗?', '亲,这款脚垫采用的是TPE环保材质,通过SGS检测无甲醛无异味,孕妇小孩都可以放心使用。相比传统PVC脚垫更环保耐用,冬不开裂夏不发软。脚垫有黑色棕色灰色可选,建议选深色更耐脏。一套包含主驾副驾后排连体,原车卡扣安装5分钟搞定。质保三年,开裂变形免费补发。' AS answer, '脚垫,异味,孕妇,SGS,环保' AS tags, '脚垫孕妇安全与环保话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_decor', '座套需要拆座椅安装吗?我自己能装吗?', '亲,这款座套是免拆座椅设计的,自己就能装。套装包含前排2个加后排1体式,配有安装图解和视频教程。前排套上去拉紧松紧带固定卡扣即可,后排需掀起坐垫塞入固定带。一般20到30分钟完成,建议两人协作更省力。座套适配95%车型,特殊车型可备注我帮您确认。' AS answer, '座套,安装,免拆座椅,教程,适配' AS tags, '座套免拆安装话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_decor', '香水留香多久?味道会不会太浓呛人?', '亲,固体香膏款留香2到3个月,液体款1到2个月,可重复添加补充液。味道是淡香型不会呛人,前调清新后调沉稳。新车建议选海洋或绿茶味去异味效果好,老车选檀香古龙更有格调。使用时打开盖子撕开密封膜,盖子可调节散香浓度。建议放在中控台或杯架,避免阳光直晒。' AS answer, '香水,留香,浓度,淡香,补充液' AS tags, '香水留香与香型选择话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_decor', '方向盘套用久了会不会松垮移位?手汗多防滑吗?', '亲,这款方向盘套内置防滑硅胶颗粒加真皮缝线,长期使用不松垮不移位。手汗多建议选打孔真皮款透气防滑效果更好。安装时套入后用手掌推紧,初次会偏紧属于正常现象,使用几天后会更贴合。M码适配37cm方向盘,L码适配38cm。建议拍下时备注车型,我帮您确认尺寸。' AS answer, '方向盘套,松垮,手汗,防滑,打孔' AS tags, '方向盘套防滑与贴合话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_decor', '檀木挂件是真材实料吗?会不会掉色?', '亲,我们这款挂件用的是天然老山檀木,配有鉴定证书可扫码查验。檀木本身不掉色不上漆,越用越包浆越亮。挂绳是手工编织的,纯铜配件不生锈。每件纹理略有不同属于天然特征。建议避免长时间暴晒和泡水。礼盒包装送人自用都体面,质保五年开裂免费换新。' AS answer, '挂件,檀木,真材实料,包浆,证书' AS tags, '檀木挂件真伪与保养话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_decor', '车身贴纸防水吗?下雨天会不会脱落?', '亲,这款贴纸是户外级PVC材质,防水防晒防褪色,下雨天不会脱落,质保3年。贴的时候车身要清洁干燥,温度10度以上施工效果最佳。贴好后用刮卡排出气泡,24小时内避免洗车。我们有车贴、车身拉花、后挡风贴纸等多种款式,支持定制LOGO和图案,起订量10张起。' AS answer, '贴纸,防水,脱落,PVC,防晒' AS tags, '贴纸防水与施工话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_decor', '脚垫耐脏吗?脏了怎么清洗?', '亲,TPE材质防水耐脏,泥水抖一抖擦一擦就干净,深度清洁用水冲或湿布擦即可,不用拆洗。比丝圈脚垫好打理多了。建议深色系更耐脏,浅色显档次但易脏。脚垫有防滑纹路设计,鞋底踩上去不滑。一套包含主副驾加后排连体,原车卡扣安装,5分钟搞定,质保三年。' AS answer, '脚垫,耐脏,清洗,TPE,防滑' AS tags, '脚垫耐脏与清洗话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_decor', '这款座套适合我的哈弗H6吗?SUV通用吗?', '亲,通用款座套适配95%轿车和SUV,哈弗H6完全没问题。建议选L码SUV专用款,包裹性更好。下单时备注您的车型和年款,我帮您确认适配。座套采用高弹松紧带加卡扣固定,安装后不移位不翘边。深色内饰建议选黑色灰色显档次,米色内饰选棕色搭配更协调。' AS answer, '座套,哈弗H6,SUV,通用,适配' AS tags, '座套SUV适配话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_decor', '香水座放杯架里尺寸合适吗?会不会太大?', '亲,这款香水座直径6.5cm高9cm,标准杯架尺寸完全适配,不会太大。重量约150g放杯架稳固不晃动。也可以放中控台或仪表台,底部有防滑垫。固体香膏款更安全不会漏液,液体款用防漏阀芯设计。香味有6种可选,留香2到3个月可重复添加。建议夏天选固体款更稳妥。' AS answer, '香水,杯架,尺寸,固体,防漏' AS tags, '香水座尺寸与杯架适配话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_decor', '真皮方向盘套手缝款难不难?需要自己缝吗?', '亲,手缝款需要自己缝制,配有针线加图解教程加视频指导,新手1到2小时可完成。手缝款包裹性更好更贴合方向盘,长期使用不松垮。如果嫌麻烦可以选免缝套入款,5分钟搞定但包裹性稍差。建议手缝款选打孔真皮透气防滑效果好。M码适配37cm,L码适配38cm方向盘。' AS answer, '方向盘套,手缝,教程,打孔,尺寸' AS tags, '手缝方向盘套DIY话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_decor', '挂件有礼盒包装吗?送人合适吗?', '亲,这款挂件配精美礼盒加手提袋,送人自用都体面。檀木款配鉴定证书,水晶款配擦布和保养油。每件独立包装防刮花。挂件长度8cm不挡视线,挂绳可调节长度。天然檀木越用越包浆,纯铜配件不生锈。建议父亲节送长辈选檀木款,送朋友选水晶款寓意好。质保五年。' AS answer, '挂件,礼盒,送人,檀木,水晶' AS tags, '挂件礼盒送礼话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_decor', '贴纸能定制LOGO吗?起订量多少?多久发货?', '亲,支持定制LOGO和图案,起订量10张起。提供AI或CDR矢量图稿即可,单色印刷3天发货,彩色5天发货。材质是户外级PVC防水防晒,质保3年不褪色。也可选现成图案100多种,单张也能拍。建议批量定制更优惠,50张以上有折扣。拍下后联系客服发图稿确认。' AS answer, '贴纸,定制,LOGO,起订量,发货' AS tags, '贴纸定制LOGO话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_decor', '脚垫有后备箱垫吗?想买全套一起换。', '亲,有后备箱垫的,可以一起拍套装更优惠。全套装包含主副驾加后排连体加后备箱垫,原车1比1开模专车专用。后备箱垫高包边设计,防止物品滚落弄脏内饰。TPE材质防水耐脏易清洗。下单时备注车型年款排量,我帮您核对车型库。套装比单买便宜80元,质保三年。' AS answer, '脚垫,后备箱垫,套装,专车专用,TPE' AS tags, '脚垫后备箱套装话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_decor', '座套有哪些颜色可选?会不会掉色?', '亲,座套有黑色、灰色、米色、棕色、红色5色可选,采用环保活性染色工艺不掉色不褪色。建议深色内饰选黑色灰色显档次耐脏,米色内饰选棕色搭配协调。新座套建议首次清洗用盐水固色。PU皮材质耐脏易打理,湿布擦拭即可。后排连体设计适配95%车型,质保两年。' AS answer, '座套,颜色,掉色,染色,耐脏' AS tags, '座套颜色与不掉色话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_decor', '香水孕妇能用吗?有酒精成分安全吗?', '亲,这款香水用的是植物萃取精油,酒精含量极低,孕妇和小孩都可以放心使用。固体香膏款比液体款更温和,建议孕妇优先选固体款。香味是淡香型不刺鼻,前调清新后调沉稳。建议放在中控台或杯架,避免阳光直晒。留香2到3个月可重复添加补充液。我们提供6种香味可选。' AS answer, '香水,孕妇,酒精,植物萃取,安全' AS tags, '香水孕妇安全话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_decor', '方向盘套新装有点紧正常吗?会不会装不上?', '亲,新装偏紧属于正常现象,真皮款需要几天时间磨合会更贴合方向盘。安装时建议先套顶部再往两侧按压,最后用掌心推到底。内置硅胶防滑颗粒,越用越贴合不移位。如果实在装不上可以联系客服,我们提供安装视频指导。M码37cm,L码38cm,建议备注车型确认尺寸。' AS answer, '方向盘套,紧,磨合,安装,尺寸' AS tags, '方向盘套偏紧化解话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_decor', '挂件需要开光吗?有开光证书吗?', '亲,这款檀木挂件是寺庙开光款,配有开光证书和高僧加持法印。水晶款是天然水晶每件有鉴定证书。挂件长度8cm不挡视线,挂绳可调节长度。天然檀木越用越包浆,纯铜配件不生锈。建议挂后视镜下方,底部距中控台保留15cm以上。礼盒包装送人自用都体面,质保五年。' AS answer, '挂件,开光,证书,檀木,水晶' AS tags, '挂件开光证书话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_decor', '贴纸夏天高温会不会起边?耐温度多少?', '亲,这款贴纸是户外级PVC材质,耐温零下20度到80度,夏天暴晒也不会起边褪色,质保3年。贴的时候车身要清洁干燥,温度10度以上施工效果最佳。贴好后24小时内避免洗车,1周内避免高压水枪直冲。我们有车贴、拉花、后挡风等多种款式,支持定制,起订量10张。' AS answer, '贴纸,高温,起边,耐温,PVC' AS tags, '贴纸耐高温话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_decor', '脚垫卡扣损坏能补发吗?质保多久?', '亲,脚垫质保三年,卡扣损坏、开裂变形、脱胶等问题都免费补发。请拍照发客服说明问题,1到3个工作日内补发。脚垫采用原车卡扣设计无损安装,正常使用不会损坏。TPE材质耐磨损不开裂,防水耐脏易清洗。建议深色系更耐脏,一套包含主副驾加后排连体,质保三年。' AS answer, '脚垫,卡扣,补发,质保,TPE' AS tags, '脚垫卡扣质保补发话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_decor', '座套夏天坐着透气吗?会不会闷热出汗?', '亲,这款座套有透气款和冰丝款可选。冰丝款夏天坐感凉爽透气不闷热,推荐南方用户选择。PU皮款建议选打孔款透气性更好。座套采用高弹松紧带加卡扣固定,安装后不移位不翘边。深色内饰选黑色显档次,米色内饰选棕色搭配协调。后排连体设计适配95%车型,质保两年。' AS answer, '座套,透气,冰丝,闷热,打孔' AS tags, '座套透气与冰丝话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_decor', '香水酒精含量高吗?车内密闭安全吗?', '亲,这款香水酒精含量极低,植物萃取精油配方,车内密闭使用安全。固体香膏款几乎不含酒精,更温和适合孕妇小孩。液体款用防漏阀芯设计,倒置不漏。香味是淡香型不刺鼻,前调清新后调沉稳。建议放在中控台或杯架,避免阳光直晒。留香2到3个月可重复添加补充液。' AS answer, '香水,酒精,密闭,安全,植物萃取' AS tags, '香水酒精含量与安全话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_decor', '方向盘套手缝款针线颜色可选吗?缝制效果好看吗?', '亲,手缝款针线颜色有红、黑、白、灰、蓝5色可选,建议选与方向盘对比色更显个性。配有专用弯针加尼龙线加图解教程加视频指导,新手1到2小时可完成。手缝款包裹性更好更贴合,长期使用不松垮。建议选打孔真皮透气防滑效果好。M码37cm,L码38cm方向盘。' AS answer, '方向盘套,手缝,针线,颜色,打孔' AS tags, '手缝方向盘套配色话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_decor', '挂件重量会不会影响后视镜?开车晃动吗?', '亲,这款挂件重量约80g,不会影响后视镜稳定性,也不会遮挡视线。挂绳是手工编织的,纯铜配件不生锈。挂件长度8cm,建议底部距中控台保留15cm以上。天然檀木越用越包浆,水晶款配鉴定证书。每件独立礼盒包装送人自用都体面。建议挂后视镜下方居中位置。' AS answer, '挂件,重量,后视镜,晃动,檀木' AS tags, '挂件重量与后视镜话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_decor', '贴纸贴在车身哪个位置最合适?有什么讲究?', '亲,车贴建议贴在后挡风玻璃下方、车身侧门、后备箱盖等位置,避免遮挡驾驶员视线。前挡风玻璃不建议贴。贴之前车身要清洁干燥,温度10度以上施工效果最佳。贴好后24小时内避免洗车。我们有车贴、拉花、个性标语等多种款式,支持定制LOGO和图案,起订量10张。' AS answer, '贴纸,位置,施工,挡风玻璃,定制' AS tags, '贴纸位置建议话术' AS source_summary, 82 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 2. 汽车配件 auto_parts (30 条) ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.60', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'auto_parts' AS code, '这款雨刷适配我的大众朗逸吗?尺寸是多少?' AS question, '亲,这款雨刷适配大众朗逸全系,主驾24寸副驾16寸,下单默认发适配尺寸。如果您是其他车型,请备注车型年款我帮您确认。无骨雨刷静音贴合玻璃,镀膜层雨天视野更清晰。质保1年,刮不干净免费补发。建议雨刷一年一换,避免橡胶老化刮花玻璃。' AS answer, '雨刷,朗逸,尺寸,无骨,镀膜' AS tags, '雨刷车型适配话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_parts', '灯泡型号我的车能用吗?怎么选?', '亲,灯泡型号很多,常见的有H1、H4、H7、H11、9005、9006等。请打开机盖看一下原车灯泡底座标注的型号,或备注车型年款我帮您查询。这款是H7型号,适配大众速腾、朗逸、迈腾等车型。LED款比卤素亮3倍寿命长5倍,建议一对一起换避免色温差。质保2年。' AS answer, '灯泡,型号,H7,LED,适配' AS tags, '灯泡型号选择话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_parts', '轮胎规格205/55R16是什么意思?我的车能换吗?', '亲,205代表胎宽205mm,55代表扁平比55%,R代表子午线轮胎,16代表轮毂尺寸16寸。换轮胎前请确认原车规格一致,不能随意改规格影响车速和ABS。这款是知名品牌全新胎,生产日期3个月内,质保3年。建议四条一起换更安全,做动平衡。我们有安装服务可选。' AS answer, '轮胎,规格,205/55R16,动平衡,质保' AS tags, '轮胎规格解读话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_parts', '机油5W-30和5W-40有什么区别?我的车该用哪个?', '亲,5W-30和5W-40代表粘度等级。5W-30省油适合日系车新车,5W-40保护性好适合德系车或老车。请参考车主手册推荐粘度,或备注车型我帮您查询。这款是全合成机油,1万公里或1年更换一次。建议4S店或正规店保养,避免假机油。我们有正品防伪可扫码验证。' AS answer, '机油,5W-30,5W-40,粘度,全合成' AS tags, '机油粘度选择话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_parts', '空调滤芯适配我的车吗?活性炭款有必要吗?', '亲,空调滤芯是专车专用的,请备注车型年款我帮您确认。活性炭款比普通款多了吸附异味和有害气体功能,建议新车和家有小孩选活性炭款。建议1万公里或1年更换一次,雾霾地区半年换一次。自己就能换,一般在手套箱后方或机盖下。配有安装图解,5分钟搞定。' AS answer, '滤芯,空调,活性炭,适配,更换' AS tags, '空调滤芯活性炭话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_parts', '火花塞铱金和铂金有什么区别?我的车该用哪种?', '亲,铱金火花塞点火性能更好寿命更长,能用8到10万公里,铂金4到6万公里。请备注车型年款我帮您确认型号和热值,不能乱用影响点火。这款是NGK铱金款,适配大众丰田本田等常见车型。建议4个一起换避免动力不均。自己换需扭矩扳手,建议4S店更换更安全。' AS answer, '火花塞,铱金,铂金,寿命,型号' AS tags, '火花塞铱金铂金对比话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_parts', '雨刷刮起来有异响怎么回事?是雨刷问题吗?', '亲,雨刷异响常见原因:第一,橡胶老化发硬,建议1年一换;第二,玻璃有油膜,用除油膜剂清洗;第三,雨刷臂角度偏了,需调整;第四,无骨雨刷压力不够。这款是硅胶镀膜款,静音贴合玻璃,质保1年刮不干净免费补发。建议雨刷竖起避免长期压玻璃老化。下单备注车型发适配尺寸。' AS answer, '雨刷,异响,油膜,镀膜,老化' AS tags, '雨刷异响排查话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_parts', 'LED灯泡需要解码器吗?会不会报故障码?', '亲,部分车型换LED需要解码器避免仪表盘报故障灯,比如大众朗逸、速腾等。这款车配CANBUS解码即插即用,不报故障码。LED比卤素亮3倍寿命长5倍,色温6000K白光更清晰。建议一对一起换避免色温差。安装时注意正负极,原车卤素直接替换,无需改线。质保2年。' AS answer, 'LED,解码器,故障码,CANBUS,色温' AS tags, 'LED灯泡解码器话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_parts', '轮胎是全新的吗?生产日期是什么时候?', '亲,这款是全新正品轮胎,生产日期3个月内,DOT标识清晰可查。轮胎侧壁有4位生产日期代码,比如2523代表2023年第25周。建议生产日期3年内的轮胎,超过3年橡胶老化不安全。我们有正品防伪可扫码验证,质保3年。建议四条一起换更安全,做动平衡和四轮定位。' AS answer, '轮胎,全新,生产日期,DOT,质保' AS tags, '轮胎全新与生产日期话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_parts', '机油是真的吗?怎么辨别真假?', '亲,我们是品牌授权经销商,正品保证假一赔十。每瓶有防伪码可扫码查验,也可拨打官方电话验证。建议从正规渠道购买避免假机油损坏发动机。这款是全合成机油,1万公里或1年更换。粘度5W-30适合日系新车,5W-40适合德系或老车。请备注车型我帮您确认。' AS answer, '机油,真假,防伪,正品,授权' AS tags, '机油真假辨别话术' AS source_summary, 92 AS score
  UNION ALL SELECT 'auto_parts', '滤芯是原厂件吗?副厂质量怎么样?', '亲,这款是品牌副厂件,质量接近原厂价格更实惠。原厂件价格贵3到5倍,副厂件性价比更高。我们有曼牌、马勒、博世等品牌可选,都是大厂品质有保障。建议1万公里或1年更换一次。请备注车型年款我帮您确认型号。自己换很简单,配有安装图解5分钟搞定。' AS answer, '滤芯,原厂,副厂,品牌,性价比' AS tags, '滤芯原厂副厂对比话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_parts', '火花塞间隙需要调整吗?热值要一样吗?', '亲,火花塞间隙和热值必须与原车一致,不能乱调影响点火。这款是出厂调好的标准间隙,无需调整。热值请参考原车火花塞型号或车主手册。建议选NGK或电装铱金款,寿命8到10万公里。4个一起换避免动力不均。自己换需扭矩扳手,建议4S店更换更安全。质保2年。' AS answer, '火花塞,间隙,热值,型号,NGK' AS tags, '火花塞间隙热值话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_parts', '有骨雨刷和无骨雨刷哪个好?我的车能用吗?', '亲,无骨雨刷贴合玻璃更好静音效果好,适合大多数车型。有骨雨刷压力大适合越野车或大玻璃。这款车是无骨款适配95%车型,下单备注车型发适配尺寸。硅胶镀膜层雨天视野更清晰,质保1年刮不干净免费补发。建议一年一换避免橡胶老化。前挡24寸后挡16寸通用。' AS answer, '雨刷,有骨,无骨,镀膜,适配' AS tags, '有骨无骨雨刷对比话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_parts', '卤素灯直接换LED能过年检吗?需要改大灯吗?', '亲,年检主要查光型和亮度,这款车是带透镜设计,光型规整年检没问题。LED比卤素亮3倍寿命长5倍,色温6000K白光更清晰。建议选带解码器的款避免故障灯,原车卤素直接替换无需改线。一对一起换避免色温差。部分地区年检严格,建议提前咨询当地检测站。质保2年。' AS answer, '卤素,LED,年检,透镜,解码器' AS tags, '卤素换LED年检话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_parts', '轮胎质保多久?鼓包能换吗?', '亲,轮胎质保3年,非人为损坏的鼓包、脱层、爆胎等问题免费换新。请保留购买凭证和轮胎DOT码。这款是全新正品胎,生产日期3个月内。建议定期检查胎压2.3到2.5bar,避免过坑减速带减速。四条一起换更安全,做动平衡和四轮定位。我们有正品防伪可扫码验证。' AS answer, '轮胎,质保,鼓包,胎压,DOT' AS tags, '轮胎质保鼓包话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_parts', '机油一桶多少升?我的车需要几桶?', '亲,这款机油是4L装,大多数4缸车需要4L左右。请参考车主手册或备注车型我帮您查询。日系车一般3.5到4L,德系车4到5L,6缸车需6到7L。建议多备0.5L备用补充。全合成机油1万公里或1年更换。粘度5W-30适合日系新车,5W-40适合德系或老车。正品防伪可扫码。' AS answer, '机油,容量,4L,车型,粘度' AS tags, '机油容量选择话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_parts', '空滤多久换一次?自己能换吗?', '亲,空气滤芯建议1万公里或1年更换,雾霾地区半年换一次。自己换很简单,打开机盖找到空滤盒,松开卡扣取出旧件换新即可,5分钟搞定。配有安装图解。请备注车型年款我帮您确认型号。这款是品牌副厂件质量接近原厂价格更实惠。建议同时换空调滤芯,空气更清新。' AS answer, '空滤,更换周期,DIY,品牌,空调滤芯' AS tags, '空滤更换DIY话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_parts', '火花塞热值不对会怎样?怎么选?', '亲,火花塞热值必须与原车一致,热值不对会导致积碳或烧蚀。请参考原车火花塞型号或车主手册,或备注车型年款我帮您查询。建议选NGK或电装铱金款,寿命8到10万公里。4个一起换避免动力不均。自己换需扭矩扳手,建议4S店更换更安全。质保2年假一赔十。' AS answer, '火花塞,热值,积碳,烧蚀,NGK' AS tags, '火花塞热值选择话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_parts', '雨刷冬天会冻硬吗?北方适合用吗?', '亲,这款是硅胶镀膜款,耐低温零下30度不变硬,北方完全适用。建议下雪天把雨刷竖起避免冻在玻璃上。无骨雨刷贴合玻璃静音效果好,镀膜层雨天视野更清晰。质保1年刮不干净免费补发。下单备注车型发适配尺寸,前挡24寸后挡16寸通用。建议一年一换避免老化。' AS answer, '雨刷,冬天,冻硬,北方,镀膜' AS tags, '雨刷北方冬季话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_parts', '卤素灯换LED需要透镜吗?不改透镜行吗?', '亲,原车带透镜直接换LED效果最佳,光型规整不晃对向来车。原车无透镜建议加装,否则光型散影响年检。这款车是360度发光设计,光型接近原车卤素,年检基本没问题。LED比卤素亮3倍寿命长5倍,色温6000K白光更清晰。一对一起换避免色温差。质保2年。' AS answer, '卤素,LED,透镜,光型,年检' AS tags, '卤素换LED透镜话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_parts', '轮胎动平衡必须做吗?不做会怎样?', '亲,换轮胎必须做动平衡,否则高速方向盘抖动影响行车安全。建议去正规轮胎店或4S店,10到20元一个轮。四条一起换建议做四轮定位,避免跑偏吃胎。这款是全新正品胎,生产日期3个月内,质保3年。定期检查胎压2.3到2.5bar。我们有正品防伪可扫码验证。' AS answer, '轮胎,动平衡,四轮定位,抖动,胎压' AS tags, '轮胎动平衡必要性话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_parts', '机油品牌怎么选?美孚壳牌嘉实多哪个好?', '亲,三大品牌都是大厂品质,美孚动力性好适合德系,壳牌清洁性好适合日系,嘉实多保护性好适合涡轮增压。建议选符合ACEA或API认证的全合成机油。1万公里或1年更换。粘度5W-30适合日系新车,5W-40适合德系或老车。请备注车型我帮您推荐。正品防伪可扫码。' AS answer, '机油,美孚,壳牌,嘉实多,认证' AS tags, '机油品牌选择话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_parts', '空调滤芯活性炭和普通款区别大吗?有必要选活性炭吗?', '亲,活性炭款比普通款多了吸附甲醛、异味、PM2.5功能,建议新车和家有小孩选活性炭款。普通款过滤花粉灰尘够用。建议1万公里或1年更换,雾霾地区半年换一次。自己换很简单,一般在手套箱后方。请备注车型年款我帮您确认型号。配有安装图解5分钟搞定。' AS answer, '滤芯,活性炭,普通,甲醛,PM2.5' AS tags, '空调滤芯活性炭必要性话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_parts', '铱金火花塞真的能用10万公里吗?寿命这么长?', '亲,铱金火花塞寿命8到10万公里,比普通镍合金3到4万公里长2到3倍。铱金熔点高耐磨损点火性能好。建议选NGK或电装品牌,质量稳定。4个一起换避免动力不均。自己换需扭矩扳手和专用套筒,建议4S店更换更安全。请备注车型年款我帮您确认型号和热值。质保2年。' AS answer, '火花塞,铱金,寿命,NGK,电装' AS tags, '铱金火花塞寿命话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_parts', '后雨刷尺寸多少?我的SUV能装吗?', '亲,后雨刷尺寸因车型而异,常见12到16寸。请备注车型年款我帮您确认,或测量原车雨刷长度。这款是专用后雨刷适配大众途观、丰田RAV4、本田CRV等SUV。无骨雨刷静音贴合玻璃,质保1年刮不干净免费补发。建议一年一换避免橡胶老化。安装很简单卡扣式5分钟。' AS answer, '后雨刷,尺寸,SUV,无骨,卡扣' AS tags, '后雨刷SUV适配话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_parts', '刹车灯泡型号是什么?我的车能换LED吗?', '亲,刹车灯泡常见型号P21/5W、P21W、W16W等,请打开灯罩看原车标注或备注车型。这款车是P21/5W LED即插即用,比卤素亮响应快更安全。一对一起换避免亮度差。安装时注意正负极,原车直接替换无需改线。LED寿命长5万小时不用换。质保2年。' AS answer, '刹车灯泡,型号,LED,P21/5W,即插即用' AS tags, '刹车灯泡换LED话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_parts', '防滑链怎么装?我的车轮胎205/55R16能用吗?', '亲,防滑链是按轮胎规格选的,205/55R16适配。请确认您的轮胎规格,打开油箱盖或车门B柱有标注。安装时驱动轮装防滑链,前驱车装前轮后驱车装后轮。建议雪天时速不超过30km/h,无雪路段及时拆卸。这款是锰钢防滑链耐用抓地力强。建议一对一起买更安全。' AS answer, '防滑链,安装,轮胎规格,锰钢,雪天' AS tags, '防滑链安装与规格话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_parts', '变速箱油我的车用哪种?多久换一次?', '亲,变速箱油分手动MT、自动AT、CVT、双离合DSG等,请备注车型年款我帮您确认。一般6万公里或3年更换,恶劣路况4万公里换。AT用ATF油,CVT用NS-2或NS-3油,DSG用专用油。建议4S店更换需专业设备循环更换。这款是原厂规格正品保证。质保1年。' AS answer, '变速箱油,AT,CVT,DSG,更换周期' AS tags, '变速箱油选择话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_parts', '汽油滤芯多久换一次?在哪个位置?', '亲,汽油滤芯一般3到4万公里或2年更换。位置因车型而异,有的在油箱内一体式,有的在底盘油管上单独式。内置式更换复杂建议4S店,外置式自己能换。请备注车型年款我帮您确认型号和位置。这款是品牌副厂件质量接近原厂价格更实惠。建议去正规店更换更安全。' AS answer, '汽油滤芯,更换周期,位置,品牌,副厂' AS tags, '汽油滤芯更换话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_parts', '刹车片多久换?前轮后轮一起换吗?', '亲,刹车片一般3到5万公里更换,具体看磨损报警片或厚度小于3mm就换。建议前轮后轮分开换,前轮磨损快先换。这款车是陶瓷刹车片低噪音少粉尘,适配大众丰田本田等常见车型。请备注车型年款我帮您确认型号。建议4S店更换需专业工具,质保2年。' AS answer, '刹车片,更换周期,前轮后轮,陶瓷,适配' AS tags, '刹车片更换话术' AS source_summary, 86 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 3. 汽车电子 auto_electronics (30 条) ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.60', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'auto_electronics' AS code, '这款行车记录仪分辨率多少?夜视效果好吗?' AS question, '亲,这款是4K超清分辨率,索尼IMX335传感器夜视效果好。F1.8大光圈加HDR宽动态,暗光环境下也能清晰拍清车牌。170度广角覆盖6车道,2.4寸屏随时回放。内置G-sensor碰撞锁定紧急视频,循环录制不漏秒。支持停车监控24小时守护爱车。质保2年,免费换新。' AS answer, '记录仪,4K,夜视,广角,G-sensor' AS tags, '行车记录仪分辨率夜视话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_electronics', '导航地图怎么升级?需要付费吗?', '亲,导航地图终身免费升级,连接WiFi自动更新。我们用的是高德地图车机版,实时路况精准导航。10.1寸大屏电容触控流畅不卡顿。支持蓝牙电话、倒车影像、手机互联。建议每3到6个月更新一次地图。安装简单原车屏位替换不动原车线路,质保2年。' AS answer, '导航,升级,免费,高德,WiFi' AS tags, '导航地图升级话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达需要打孔吗?安装复杂吗?', '亲,这款车是无线倒车雷达,后保险杠打4个孔安装探头。建议4S店或汽车装饰店安装,工时费50到100元。也可以选贴片式免打孔,直接贴保险杠更简单。雷达探测距离0.3到2.5米,蜂鸣报警三段式提示。LED数字显示距离更直观。适配95%车型,质保2年。' AS answer, '倒车雷达,打孔,无线,探头,安装' AS tags, '倒车雷达安装话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '车载充电器快充吗?我的手机能用吗?', '亲,这款车载充电器支持PD30W加QC3.0双口快充,iPhone华为小米都适用。点烟器接口通用12V/24V,轿车货车都能用。智能芯片温控保护不伤电池。建议选带电压监测款,随时查看电瓶状态。我们有单口双口四口可选,多设备同时充。质保1年,免费换新。' AS answer, '充电器,快充,PD30W,QC3.0,电压' AS tags, '车载充电器快充话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱功耗大吗?会亏电瓶吗?', '亲,这款车载冰箱功耗45W相当于一个灯泡,正常使用不会亏电瓶。有车用12V和家用220V两用,出门家里都能用。制冷零下20度到20度可调,保温保冷两用。建议停车超过2小时拔电避免电瓶亏电。容量10L15L20L可选,能放12罐可乐。低噪音38分贝不影响休息。质保2年。' AS answer, '车载冰箱,功耗,亏电,12V,220V' AS tags, '车载冰箱功耗话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_electronics', '行车记录仪有电池吗?夏天高温会爆吗?', '亲,这款车载记录仪内置超级电容无锂电池,夏天暴晒70度也不会爆炸更安全。建议选带停车监控线款,24小时守护爱车。4K超清索尼传感器夜视效果好,F1.8大光圈暗光也能拍清车牌。170度广角覆盖6车道。循环录制不漏秒,G-sensor碰撞锁定。质保2年免费换新。' AS answer, '记录仪,电池,电容,高温,爆炸' AS tags, '记录仪电池与高温话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_electronics', '导航流量卡怎么用?需要单独买流量吗?', '亲,导航内置4G模块配流量卡,首年免费送2G/月,次年可续费。WiFi联网也能用手机热点。高德地图实时路况精准导航,在线音乐有声读物娱乐丰富。10.1寸大屏电容触控流畅。建议每月2G够用,频繁在线视频建议办大流量卡。安装原车屏位替换,质保2年。' AS answer, '导航,流量卡,4G,WiFi,高德' AS tags, '导航流量卡话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达几个探头好?4个够吗?', '亲,4个探头覆盖后保险杠够用,6个探头两侧多2个探测更全面。建议SUV和长车身选6个,轿车4个够用。这款车是无线倒车雷达,LED数字显示距离蜂鸣报警三段式提示。探测距离0.3到2.5米。后保险杠打孔安装,建议4S店工时费50到100元。质保2年免费换新。' AS answer, '倒车雷达,探头,4个,6个,SUV' AS tags, '倒车雷达探头数量话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_electronics', '车载充电器PD30W我的iPhone能快充吗?', '亲,PD30W支持iPhone12及以上机型快充,30分钟充50%电量。QC3.0口支持安卓快充。双口同充智能分配电流。点烟器接口通用12V/24V,轿车货车都能用。智能芯片温控保护不伤电池。建议选带电压监测款随时查看电瓶状态。质保1年免费换新。' AS answer, '充电器,PD30W,iPhone,快充,QC3.0' AS tags, '车载充电器iPhone快充话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱能制冷到多少度?夏天能用吗?', '亲,这款车载冰箱制冷零下20度到20度可调,夏天制冷到0度以下没问题。压缩机制冷比半导体制冷效果好速度快。车用12V和家用220V两用,出门家里都能用。容量10L能放12罐可乐。低噪音38分贝不影响休息。建议停车超2小时拔电避免电瓶亏电。质保2年。' AS answer, '车载冰箱,制冷,压缩机,夏天,12V' AS tags, '车载冰箱制冷话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_electronics', '行车记录仪停车监控怎么用?会亏电瓶吗?', '亲,停车监控需接降压线直连电瓶,记录仪进入低功耗模式,碰撞自动唤醒录制。建议选带电压保护款,电瓶电压低于11.6V自动断电保护不打火。正常停车1周不会亏电瓶。4K超清索尼传感器夜视效果好,170度广角覆盖6车道。G-sensor碰撞锁定紧急视频。质保2年。' AS answer, '记录仪,停车监控,降压线,亏电,电压保护' AS tags, '记录仪停车监控话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_electronics', '导航有倒车影像吗?后摄怎么安装?', '亲,导航支持倒车影像,配后摄摄像头。后摄安装在后保险杠或牌照灯位置,建议4S店或装饰店安装工时费50到100元。10.1寸大屏倒车影像更清晰,支持轨迹线辅助。导航原车屏位替换不动线路。高德地图实时路况精准导航,蓝牙电话手机互联。质保2年免费换新。' AS answer, '导航,倒车影像,后摄,安装,轨迹线' AS tags, '导航倒车影像话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达无线和有线区别大吗?无线稳定吗?', '亲,无线倒车雷达安装更简单不用穿线到驾驶室,但需要外接电源。有线更稳定信号无干扰,但安装复杂需要走线。这款车是无线款,LED数字显示距离蜂鸣报警三段式提示。探测距离0.3到2.5米。后保险杠打4个孔安装,建议4S店工时费50到100元。质保2年免费换新。' AS answer, '倒车雷达,无线,有线,安装,稳定' AS tags, '倒车雷达无线有线对比话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_electronics', '车载无线充电器我的手机能用吗?带快充吗?', '亲,无线充电支持Qi协议,iPhone8及以上、华为小米旗舰都适用。10W快充比普通5W快2倍。自动夹紧手机支持横竖屏导航。点烟器接口通用12V/24V。建议手机戴壳厚度不超过5mm。智能芯片温控保护不伤电池。出风口和吸盘两种安装方式可选。质保1年免费换新。' AS answer, '无线充电,Qi协议,10W,快充,夹紧' AS tags, '车载无线充电器话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱家用220V能用吗?耗电吗?', '亲,这款车载冰箱车用12V和家用220V两用,出门家里都能用。功耗45W相当于一个灯泡,一天约1度电很省。压缩机制冷零下20度到20度可调,保温保冷两用。容量10L能放12罐可乐。低噪音38分贝不影响休息。建议停车超2小时拔电避免电瓶亏电。质保2年免费换新。' AS answer, '车载冰箱,220V,家用,耗电,压缩机' AS tags, '车载冰箱家用话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '行车记录仪夜视效果怎么样?晚上能拍清车牌吗?', '亲,这款是4K超清索尼IMX335传感器,F1.8大光圈加HDR宽动态,晚上路灯下能清晰拍清车牌。170度广角覆盖6车道,2.4寸屏随时回放。内置G-sensor碰撞锁定紧急视频,循环录制不漏秒。支持停车监控24小时守护。内置超级电容无锂电池夏天不爆。质保2年。' AS answer, '记录仪,夜视,车牌,4K,索尼' AS tags, '记录仪夜视效果话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_electronics', '导航是安卓系统吗?能装APP吗?', '亲,这款是安卓系统2加32G大内存,可装高德、QQ音乐、喜马拉雅等APP。10.1寸大屏电容触控流畅不卡顿。支持WiFi联网下载APP和升级地图。蓝牙电话手机互联倒车影像。建议不装太多APP避免卡顿。安装原车屏位替换不动原车线路。质保2年免费换新。' AS answer, '导航,安卓,APP,WiFi,蓝牙' AS tags, '导航安卓系统话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达显示距离准确吗?有声音提示吗?', '亲,这款车载倒车雷达LED数字显示距离,准确到0.1米。蜂鸣报警三段式提示:2米开始报警,1米急促报警,0.5米长鸣警告。探测距离0.3到2.5米。4个探头覆盖后保险杠,建议SUV选6个探头。后保险杠打孔安装,建议4S店工时费50到100元。质保2年免费换新。' AS answer, '倒车雷达,距离,声音,蜂鸣,探头' AS tags, '倒车雷达距离显示话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_electronics', '点烟器扩展器有几个口?能同时用吗?', '亲,这款车载点烟器扩展器有2点烟器口加2USB口加1Type-C口,可同时使用。总功率120W支持车载冰箱、吸尘器等大功率设备。独立开关分别控制省电安全。点烟器接口通用12V/24V轿车货车都能用。智能芯片过载保护。建议选带电压监测款随时查看电瓶。质保1年。' AS answer, '点烟器,扩展器,USB,Type-C,120W' AS tags, '点烟器扩展器话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱噪音大吗?放车里会影响休息吗?', '亲,这款车载冰箱低噪音38分贝相当于图书馆,不会影响休息。压缩机制冷比半导体静音效果好。制冷零下20度到20度可调,保温保冷两用。车用12V家用220V两用。容量10L能放12罐可乐。建议放在后排座椅或后备箱减震。停车超2小时拔电避免亏电。质保2年。' AS answer, '车载冰箱,噪音,压缩机,38分贝,减震' AS tags, '车载冰箱噪音话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_electronics', '行车记录仪后摄怎么安装?前后双录有用吗?', '亲,后摄安装在后挡风玻璃内侧,走线沿车顶到后备箱隐藏式安装。前后双录更全面追责有据。4K前摄加1080P后摄,索尼传感器夜视效果好。170度广角覆盖6车道。建议4S店或装饰店安装工时费100元左右。也可单前录更简单。循环录制不漏秒,G-sensor碰撞锁定。质保2年。' AS answer, '记录仪,后摄,前后双录,安装,4K' AS tags, '记录仪前后双录话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_electronics', '导航蓝牙能连手机吗?通话质量怎么样?', '亲,导航支持蓝牙5.0连接手机,通话清晰无杂音支持电话本同步。10.1寸大屏电容触控。高德地图实时路况精准导航,WiFi联网在线升级。支持手机互联投屏。建议通话时关窗减少噪音。安装原车屏位替换不动原车线路。质保2年免费换新。配后摄支持倒车影像。' AS answer, '导航,蓝牙,5.0,通话,手机互联' AS tags, '导航蓝牙通话话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达适配我的SUV吗?探头防水吗?', '亲,这款车载倒车雷达适配95%车型,SUV轿车货车都能用。探头IP67防水防尘洗车无压力。LED数字显示距离蜂鸣报警三段式提示。探测距离0.3到2.5米。4个探头覆盖后保险杠,SUV建议选6个探头更全面。后保险杠打孔安装,建议4S店工时费50到100元。质保2年。' AS answer, '倒车雷达,SUV,防水,IP67,探头' AS tags, '倒车雷达SUV适配话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_electronics', '车载充电器几个口够用?四口会分流吗?', '亲,四口充电器支持多设备同时充,单口最大30W智能分配电流不降速。2USB加2Type-C设计兼容性强。点烟器接口通用12V/24V轿车货车都能用。智能芯片温控保护不伤电池。建议选带电压监测款随时查看电瓶状态。四口适合家庭出行多设备充电。质保1年免费换新。' AS answer, '充电器,四口,分流,30W,Type-C' AS tags, '车载充电器多口话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱容量多大?能放多少东西?', '亲,这款车载冰箱有10L、15L、20L三种容量可选。10L能放12罐可乐或6瓶矿泉水。15L能放18罐可乐。20L适合自驾游露营。制冷零下20度到20度可调,保温保冷两用。车用12V家用220V两用。低噪音38分贝。建议根据用途选容量,日常通勤10L够用。质保2年。' AS answer, '车载冰箱,容量,10L,15L,20L' AS tags, '车载冰箱容量话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_electronics', '行车记录仪广角170度够吗?会不会变形?', '亲,170度广角覆盖6车道,比140度更全面。索尼IMX335传感器畸变矫正技术画面不变形。4K超清分辨率F1.8大光圈夜视效果好。2.4寸屏随时回放。循环录制不漏秒,G-sensor碰撞锁定紧急视频。内置超级电容无锂电池夏天不爆。建议停车监控接降压线。质保2年。' AS answer, '记录仪,广角,170度,变形,畸变' AS tags, '记录仪广角变形话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_electronics', '导航语音控制好用吗?识别准确吗?', '亲,这款导航支持AI语音控制,导航到某地、打电话给某人等指令识别准确。10.1寸大屏电容触控。高德地图实时路况精准导航。蓝牙5.0连接手机通话清晰。建议开车用语音操作更安全。安装原车屏位替换不动原车线路。支持WiFi联网下载APP和升级地图。质保2年。' AS answer, '导航,语音,识别,高德,蓝牙' AS tags, '导航语音控制话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_electronics', '倒车雷达探头坏了能换吗?质保多久?', '亲,倒车雷达质保2年,探头损坏免费补发。请拍照发客服说明问题。探头IP67防水防尘洗车无压力。LED数字显示距离蜂鸣报警三段式提示。探测距离0.3到2.5米。4个探头覆盖后保险杠,SUV建议选6个探头。后保险杠打孔安装,建议4S店工时费50到100元。质保2年。' AS answer, '倒车雷达,探头,坏了,质保,IP67' AS tags, '倒车雷达探头质保话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_electronics', '车载逆变器能带笔记本电脑吗?功率多大?', '亲,这款车载逆变器150W纯正弦波,能带笔记本电脑、相机充电等。点烟器接口输入12V输出220V家用。建议选纯正弦波款保护电器不损伤。总功率不要超过150W避免烧保险丝。智能芯片过载过热保护。轿车货车都能用。建议发动机启动时使用避免电瓶亏电。质保1年。' AS answer, '逆变器,150W,纯正弦波,笔记本,220V' AS tags, '车载逆变器话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_electronics', '车载冰箱保温效果怎么样?断电能保持多久?', '亲,这款车载冰箱保温层厚密度高,断电后能保持低温6到8小时。压缩机制冷零下20度到20度可调,比半导体制冷效果好。车用12V家用220V两用。容量10L15L20L可选。低噪音38分贝不影响休息。建议长时间停车拔电避免亏电。质保2年免费换新。' AS answer, '车载冰箱,保温,断电,压缩机,12V' AS tags, '车载冰箱保温话术' AS source_summary, 83 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 4. 摩托车 auto_motorcycle (30 条) ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.60', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'auto_motorcycle' AS code, '摩托车过户需要什么手续?流程复杂吗?' AS question, '亲,摩托车过户需要双方身份证、行驶证、登记证书、交强险保单,到车管所办理。流程:开新车主身份证验车缴费选号出新证。建议买卖双方一起去,避免后续纠纷。过户费100到200元。请注意排放标准,国三以下部分城市限迁。无证车辆无法过户,请先确认手续齐全。' AS answer, '摩托车,过户,手续,车管所,排放' AS tags, '摩托车过户手续话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_motorcycle', '这款头盔有3C认证吗?安全性怎么样?', '亲,这款头盔通过3C认证和DOT认证,ABS外壳加EPS缓冲层,安全性有保障。双镜片设计,内层茶色防强光。可拆卸内衬易清洗。建议选带ECE认证款更严格。头盔是保命装备不要贪便宜。请测量头围选尺码,M码57到58cm,L码59到60cm。质保1年。' AS answer, '头盔,3C认证,DOT,ABS,EPS' AS tags, '头盔3C认证话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行服尺码怎么选?我170cm 70kg穿多大?', '亲,170cm 70kg建议选L码。骑行服偏修身建议比平时大一码。这款是耐磨牛津布加护具,肩肘背都有CE认证护具。透气网眼设计夏天不闷热。建议试穿不合身可退换。护具可拆卸日常穿。尺码表:M码170/65,L码175/70,XL码180/75,2XL码185/80。质保1年。' AS answer, '骑行服,尺码,170cm,CE认证,护具' AS tags, '骑行服尺码选择话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_motorcycle', '这辆机车是国几排放?能上牌吗?', '亲,这辆车是国四电喷排放,全国可上牌。请确认当地摩托车上牌政策,部分城市限摩。上牌需要合格证、发票、身份证、交强险。建议买车前咨询当地车管所。国四电喷比国三化油器省油环保动力好。我们提供正规发票和合格证,协助上牌。质保2年或2万公里。' AS answer, '机车,国四,排放,上牌,电喷' AS tags, '机车排放上牌话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板摩托车续航多少?油箱多大?', '亲,这款踏板车油箱7L,百公里油耗2.5L,续航约280公里。电喷比化油器省油15%。建议加92号汽油即可。市区代步通勤一周一加油足够。这款车是125cc水冷发动机,动力够用静音舒适。有USB充电口手机导航不焦虑。质保2年或2万公里。提供正规发票协助上牌。' AS answer, '踏板车,续航,油箱,油耗,125cc' AS tags, '踏板车续航话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '摩托车上牌需要什么?流程复杂吗?', '亲,上牌需要合格证、发票、身份证、交强险,到车管所办理。流程:交购置税验车选号领证。购置税是车价10%除以1.13。建议买车前确认当地政策,部分城市限摩。我们提供正规发票和合格证,协助上牌。国四排放全国可上牌。建议上牌后及时办驾照和保险。' AS answer, '摩托车,上牌,购置税,合格证,车管所' AS tags, '摩托车上牌流程话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_motorcycle', '头盔蓝牙耳机怎么连手机?通话清晰吗?', '亲,这款头盔蓝牙耳机蓝牙5.0连接手机,通话清晰支持降噪。可听歌导航接电话。续航10小时满足一天骑行。防水IPX6雨天可用。通用卡扣适配全盔半盔揭面盔。建议双人对讲选mesh款距离更远。安装简单卡扣固定不破坏头盔。质保1年免费换新。' AS answer, '头盔,蓝牙,5.0,降噪,IPX6' AS tags, '头盔蓝牙耳机话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行服护具是CE认证吗?防摔效果怎么样?', '亲,这款骑行服肩肘背都有CE认证护具,防摔效果好。耐磨牛津布加网眼透气设计夏天不闷热。护具可拆卸日常穿。建议选带背部护具款保护脊椎。尺码偏修身建议比平时大一码。试穿不合身可退换。质保1年。骑行服是保命装备不要贪便宜,建议选带认证款。' AS answer, '骑行服,CE认证,护具,防摔,牛津布' AS tags, '骑行服护具认证话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_motorcycle', '机车链条怎么保养?多久上一次油?', '亲,机车链条建议500公里清洁上油一次,用专用链条油或链条蜡。清洁用链条清洁剂和刷子,擦干后均匀喷链条油。调整链条松紧度20到30mm。建议长途骑行前检查。链条磨损拉长及时更换避免断裂。这款车是O型密封链条耐用免维护。建议1万公里检查磨损。质保2年。' AS answer, '链条,保养,上油,清洁,松紧' AS tags, '机车链条保养话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板摩托车轮胎多久换?什么牌子好?', '亲,踏板车轮胎一般2万公里或3年更换,看磨损标记。建议选正新、建大、米其林等品牌。这款车配正新真空胎耐磨抓地力好。轮胎规格请参考原车,不能乱改影响操控。建议前后一起换更安全。雨天注意减速,真空胎扎钉可补。质保1年非人为损坏免费换新。' AS answer, '踏板车,轮胎,正新,真空胎,磨损' AS tags, '踏板车轮胎更换话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_motorcycle', '摩托车需要驾照吗?什么驾照能骑?', '亲,摩托车需要驾照,普通两轮E证,轻便摩托车F证,三轮D证。建议直接考D证能骑所有摩托。流程:体检报名科一理论科二场地科三路考科四理论。1到2个月拿证。无证驾驶罚款拘留扣车。请确认有驾照再买车。我们协助提供购车发票和合格证。建议买保险。' AS answer, '摩托车,驾照,E证,F证,D证' AS tags, '摩托车驾照话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_motorcycle', '头盔镜片起雾怎么办?有防雾款吗?', '亲,这款头盔配双层防雾镜片,冬天不起雾。也可买防雾贴膜或防雾喷剂。建议选揭面盔通风好。Pinlock防雾贴效果最佳。双镜片设计内层茶色防强光。可拆卸内衬易清洗。请测量头围选尺码,M码57到58cm,L码59到60cm。3C认证加DOT认证安全性有保障。质保1年。' AS answer, '头盔,镜片,起雾,防雾,Pinlock' AS tags, '头盔防雾话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行服夏天穿热吗?有透气款吗?', '亲,这款骑行服是网眼透气设计,夏天穿不闷热。肩肘背护具CE认证防摔。护具可拆卸日常穿。建议夏天选网眼款,冬天选防水保暖款。尺码偏修身建议比平时大一码。试穿不合身可退换。建议配骑行手套和骑行靴更安全。质保1年。骑行服是保命装备不要贪便宜。' AS answer, '骑行服,夏天,透气,网眼,CE认证' AS tags, '骑行服夏天透气话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_motorcycle', '机车排气管改装合法吗?年检能过吗?', '亲,排气管改装属于非法改装,年检不过会被交警查扣罚款。建议选原厂或带3C认证的排气。改装排气噪音大扰民违法。这款车是原厂静音排气符合国标。建议保留原厂排气年检无忧。如需改装请咨询当地车管所备案。质保2年。我们提供正规发票和合格证。' AS answer, '排气管,改装,合法,年检,3C' AS tags, '机车排气管改装话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板摩托车油耗多少?省油吗?', '亲,这款踏板车125cc水冷电喷,百公里油耗2.5L,比化油器省油15%。油箱7L续航280公里。建议加92号汽油。市区代步通勤一周一加油足够。电喷启动快怠速稳,水冷散热好长途不热衰。有USB充电口手机导航不焦虑。质保2年或2万公里。提供正规发票协助上牌。' AS answer, '踏板车,油耗,125cc,电喷,水冷' AS tags, '踏板车油耗话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '摩托车保险怎么买?一年多少钱?', '亲,摩托车交强险必买,150cc以下80元/年,150cc以上120元/年。建议加三者险100万约200元更保障。车损险可选。建议去保险公司或车管所买。无保险上路罚款扣车。我们协助提供购车发票和合格证办保险。建议同时办驾照和行驶证。质保2年。' AS answer, '摩托车,保险,交强险,三者险,150cc' AS tags, '摩托车保险话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_motorcycle', '头盔尺码怎么选?我头围58cm穿多大?', '亲,头围58cm建议选M码。请用软尺量眉骨上方一圈最准。尺码表:S码55到56cm,M码57到58cm,L码59到60cm,XL码61到62cm。建议试戴不夹头不松。这款3C认证加DOT认证ABS外壳加EPS缓冲层。双镜片设计,可拆卸内衬。质保1年。头盔是保命装备不要贪便宜。' AS answer, '头盔,尺码,头围,58cm,M码' AS tags, '头盔尺码选择话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行靴防水吗?冬天穿冷吗?', '亲,这款骑行靴是防水透气设计,雨天不湿脚。冬天建议选加绒款保暖。鞋底防滑耐磨,脚踝护具保护。建议选带变速垫款换挡不滑。尺码标准建议按平时鞋码。防水款四季通用,加绒款北方冬天适用。质保1年。骑行靴是保命装备不要贪便宜,建议选带CE认证款。' AS answer, '骑行靴,防水,冬天,加绒,变速垫' AS tags, '骑行靴防水话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_motorcycle', '机车电瓶多久换一次?什么牌子好?', '亲,机车电瓶一般2到3年更换,看启动是否困难。建议选汤浅、统一、博世等品牌。这款车配汤浅免维护电瓶耐用。电瓶规格请参考原车,不能乱改。建议长期停放拆电瓶线避免亏电。电瓶亏电可充电恢复,老化需更换。建议定期检查电瓶电压12.6V正常。质保1年。' AS answer, '电瓶,更换,汤浅,免维护,电压' AS tags, '机车电瓶话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板摩托车保养周期是多少?怎么保养?', '亲,踏板车保养:机油1000公里首保,之后3000公里或半年换。齿轮油5000公里换。空滤1万公里换。火花塞2万公里换。轮胎刹车片看磨损。建议去正规维修店保养。这款车是水冷电喷维护简单。质保2年或2万公里。建议保留保养记录质保有效。我们提供保养手册。' AS answer, '踏板车,保养,机油,齿轮油,空滤' AS tags, '踏板车保养周期话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_motorcycle', '摩托车年检怎么办理?几年一次?', '亲,摩托车6年内免上线检测,每2年领检验标志。6到10年每年上线检测。10年以上每半年检测。需带行驶证、交强险、身份证到检测站。建议提前3个月办理。年检主要查排放、灯光、刹车。非法改装年检不过请恢复原厂。我们提供正规发票和合格证。质保2年。' AS answer, '摩托车,年检,6年,2年,检测' AS tags, '摩托车年检话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '头盔防晒吗?夏天戴热吗?', '亲,这款头盔双镜片设计内层茶色防紫外线防强光。通风口设计夏天不闷热。建议选浅色头盔吸热少。ABS外壳加EPS缓冲层3C认证加DOT认证。可拆卸内衬易清洗。请测量头围选尺码,M码57到58cm,L码59到60cm。质保1年。建议配头盔套防晒防尘。' AS answer, '头盔,防晒,茶色,通风,3C' AS tags, '头盔防晒话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行手套防摔吗?触屏好用吗?', '亲,这款骑行手套掌心有防滑耐磨TPR护具,指关节碳纤维保护防摔。触屏指尖设计手机操作不脱手套。透气网眼夏天不闷热。建议选带护具款保护手掌。尺码偏修身建议比平时大一码。试穿不合身可退换。质保1年。骑行手套是保命装备不要贪便宜,建议选带CE认证款。' AS answer, '骑行手套,防摔,触屏,碳纤维,TPR' AS tags, '骑行手套话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '机车机油用什么粘度?多久换一次?', '亲,机车机油建议10W-40全合成,1000公里首保,之后3000公里或半年换。请参考车主手册推荐粘度。建议选摩特、壳牌、美孚等品牌。这款车是水冷四冲程发动机用10W-40。建议从正规渠道购买避免假机油损坏发动机。质保2年。我们提供保养手册和原厂配件。' AS answer, '机车,机油,10W-40,全合成,首保' AS tags, '机车机油粘度话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板摩托车电池能换锂电池吗?续航更久吗?', '亲,踏板车可以换锂电池,重量轻启动电流大,但价格贵2到3倍。原车铅酸电池性价比高,2到3年更换。建议选汤浅、统一等品牌。电池规格请参考原车不能乱改。长期停放建议拆电池线避免亏电。这款车配汤浅免维护电池耐用。质保1年。建议定期检查电池电压。' AS answer, '踏板车,电池,锂电池,铅酸,汤浅' AS tags, '踏板车电池话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_motorcycle', '摩托车托运怎么办理?多少钱?', '亲,摩托车托运建议选德邦或中铁快运,1000公里约500到800元。需排空汽油拆电瓶。建议打木架保护避免运输损伤。短途可上门提车。请保留购车发票和合格证随车。建议买运输保险。我们协助打包发货。质保2年。如自提请带身份证和尾款。提供正规发票协助上牌。' AS answer, '摩托车,托运,德邦,中铁快运,木架' AS tags, '摩托车托运话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_motorcycle', '头盔内衬怎么清洗?能拆吗?', '亲,这款头盔内衬可拆卸,用温水加中性洗涤剂手洗,阴干不要暴晒。建议1到2个月清洗一次保持卫生。ABS外壳用湿布擦拭即可,避免有机溶剂。镜片用清水或专用清洁剂擦。请测量头围选尺码。3C认证加DOT认证ABS外壳加EPS缓冲层。质保1年。建议配头盔套防尘。' AS answer, '头盔,内衬,清洗,拆卸,中性洗涤' AS tags, '头盔内衬清洗话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_motorcycle', '骑行背包防水吗?容量多大合适?', '亲,这款骑行背包是防水设计,雨天不湿。容量25L适合日常通勤和短途摩旅。多隔层设计笔记本电脑、水壶、工具分区。胸带腰带固定骑行不晃动。反光条夜骑更安全。建议长途选35L容量更大。质保1年。建议配骑行服和头盔更安全。骑行装备是保命装备不要贪便宜。' AS answer, '骑行背包,防水,25L,胸带,反光条' AS tags, '骑行背包话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_motorcycle', '机车空滤多久换?自己能换吗?', '亲,机车空滤建议1万公里或1年更换,雾霾地区半年换。自己换很简单,打开空滤盒取出旧件换新即可,5分钟搞定。请备注车型我帮您确认型号。这款车是品牌副厂件质量接近原厂价格更实惠。建议同时换机油保养效果更好。质保1年。我们提供保养手册和原厂配件。' AS answer, '机车,空滤,更换,DIY,副厂' AS tags, '机车空滤更换话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_motorcycle', '踏板车钥匙丢了能配吗?多少钱?', '亲,踏板车钥匙可以配,普通钥匙20到50元,芯片钥匙100到200元。建议去4S店或专业配钥匙店。这款车是机械钥匙通用好配。建议配2把备用避免丢失。如全丢需换锁芯约200元。质保1年。我们协助提供锁芯编码。建议钥匙和行驶证分开存放避免同时丢失。' AS answer, '踏板车,钥匙,配钥匙,芯片,锁芯' AS tags, '踏板车钥匙话术' AS source_summary, 80 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 5. 自行车 auto_bicycle (30 条) ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.60', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'auto_bicycle' AS code, '这款山地车变速器几个档位?上坡省力吗?' AS question, '亲,这款车是Shimano 21速变速,3前7后。上坡换低档省力,下坡高档省力。建议上坡前提前换挡避免损齿。变速器调校精确换挡顺滑。轮组铝合金轻量耐用,机械碟刹制动效果好。车架铝合金轻便抗锈。整车重量15kg适合骑行。建议按身高选尺码。质保3年车架。' AS answer, '山地车,变速,21速,Shimano,碟刹' AS tags, '山地车变速话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车轮组是碳纤维吗?多重?', '亲,这款车配铝合金轮组,碳纤维轮组需另购约2000元。铝合金轮组耐用性价比高,整车重量11kg。碳纤维轮组轻1kg加速快但价格贵。建议入门选铝合金,进阶升级碳纤维。轮组规格700C标准公路车。Shimano Claris 16速变速精准。质保3年车架1年轮组。' AS answer, '公路车,轮组,碳纤维,铝合金,700C' AS tags, '公路车轮组话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车续航多少公里?充满要多久?', '亲,这款车配48V20Ah锂电池,续航60到80公里。充电6到8小时充满。建议电量低于30%及时充电避免亏电。电池可拆卸室内充电。电机500W动力够用最高时速25km/h符合新国标。建议上牌后上路,需驾照以当地政策为准。整车重量55kg。质保3年车架1年电池。' AS answer, '电动车,续航,48V,锂电池,新国标' AS tags, '电动车续航话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'auto_bicycle', '车锁防盗性能怎么样?能防液压剪吗?', '亲,这款U型锁采用锰钢材质,防液压剪防撬防锯。C级锁芯防技术开启180分钟。建议选16mm锁梁以上更安全。配3把钥匙丢失可配。建议锁车架和固定物避免搬运。碟刹锁更便携适合短停。建议选带报警款威慑小偷。质保5年。建议买保险更保障。' AS answer, '车锁,U型锁,锰钢,液压剪,C级锁芯' AS tags, '车锁防盗话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_bicycle', '这款自行车多大码适合我?我175cm?', '亲,175cm建议选26寸M码车架。尺码表:S码155到165cm,M码165到180cm,L码180到195cm。建议试骑更准。这款车是铝合金车架轻便抗锈。Shimano 21速变速上坡省力。机械碟刹制动效果好。整车重量15kg。建议按身高选尺码,腿长略短选小一码。质保3年车架。' AS answer, '自行车,尺码,175cm,M码,铝合金' AS tags, '自行车尺码选择话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', '山地车碟刹和V刹哪个好?制动距离差多少?', '亲,碟刹制动力强雨天不影响,V刹轻便但雨天打滑。碟刹分机械和油压,油压更顺滑但贵。建议选机械碟刹性价比高。这款车是机械碟刹制动距离比V刹短30%。碟刹维护简单换刹车片即可。建议下坡提前刹车避免热衰减。质保3年车架1年刹车。建议定期检查刹车片。' AS answer, '山地车,碟刹,V刹,制动,油压' AS tags, '碟刹V刹对比话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车胎压多少合适?多久打一次气?', '亲,公路车胎压建议80到120psi,看轮胎标注。建议每周打一次气,胎压不足易爆胎。用带气压表的打气筒。这款车是700C细胎低阻力省力。建议选玛吉斯、维多利亚等品牌。雨天胎压略降增加抓地。建议定期检查外胎磨损避免爆胎。质保3年车架1年轮胎。备胎必备。' AS answer, '公路车,胎压,psi,打气,700C' AS tags, '公路车胎压话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车电池能取下来充电吗?续航会衰减吗?', '亲,电池可拆卸室内充电方便。锂电池500次循环后容量约80%,正常用3到5年。建议电量低于30%及时充避免亏电,长期不用每月充一次。电池质保1年。这款车48V20Ah续航60到80公里。建议夏天避免暴晒,冬天室内充电。质保3年车架1年电池。建议上牌后上路。' AS answer, '电动车,电池,可拆卸,锂电池,衰减' AS tags, '电动车电池话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_bicycle', '车锁U型锁和链条锁哪个好?各有什么优缺点?', '亲,U型锁安全性高防液压剪但较重,适合固定停放。链条锁灵活可锁固定物但易被剪,建议选锰钢材质。碟刹锁便携适合短停。建议U型锁加碟刹锁双锁更安全。这款车是U型锁锰钢C级锁芯防撬180分钟。配3把钥匙。质保5年。建议买保险更保障。锁车架和固定物。' AS answer, '车锁,U型锁,链条锁,锰钢,双锁' AS tags, 'U型锁链条锁对比话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', '这款自行车是铝合金还是碳纤维?多重?', '亲,这款车是铝合金车架,整车重量15kg。铝合金轻便抗锈性价比高适合入门。碳纤维轻1到2kg减震好但价格贵。建议入门选铝合金,进阶升级碳纤维。车架质保3年。Shimano 21速变速上坡省力。机械碟刹制动效果好。建议按身高选尺码。质保3年车架1年零件。' AS answer, '自行车,铝合金,碳纤维,重量,车架' AS tags, '自行车材质话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_bicycle', '山地车避震前叉有用吗?软硬可调吗?', '亲,避震前叉下坡和颠簸路面更舒适,平路会增加阻力。这款车是机械避震前叉软硬可调,城市通勤可锁死变硬省力。建议下坡解锁避震,平路锁死省力。前叉行程80mm适合XC越野。气叉比弹簧叉轻可调性好但贵。建议定期保养前叉。质保3年车架1年前叉。' AS answer, '山地车,避震,前叉,软硬,锁死' AS tags, '山地车避震话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车变速器Shimano Claris怎么样?够用吗?', '亲,Shimano Claris是入门级16速变速,精准顺滑够用。建议入门选Claris,进阶选105或Ultegra。这款车配Claris 16速,2前8后齿比广上坡省力。变速器调校精确换挡顺滑。建议上坡前提前换挡避免损齿。轮组700C标准公路车。质保3年车架1年变速。' AS answer, '公路车,变速,Shimano,Claris,16速' AS tags, '公路车变速话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车充电多久能充满?耗电多少?', '亲,电动车48V20Ah电池充电6到8小时充满,耗电约1度电费1元。建议电量低于30%及时充避免亏电。电池可拆卸室内充电。建议夏天避免高温充电,冬天室内充电。锂电池比铅酸轻寿命长。这款车续航60到80公里。质保3年车架1年电池。建议上牌后上路,需驾照以当地政策为准。' AS answer, '电动车,充电,充满,耗电,48V' AS tags, '电动车充电话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', 'U型锁尺寸多大?能锁车轮和固定物吗?', '亲,这款U型锁锁梁16mm,内径10x15cm能锁车架和固定物。锰钢材质防液压剪防撬防锯。C级锁芯防技术开启180分钟。配3把钥匙。建议锁车架和固定物避免搬运。也可以锁车轮碟刹。建议选带报警款威慑小偷。质保5年。建议买保险更保障。锁车架更安全。' AS answer, 'U型锁,尺寸,16mm,车架,固定物' AS tags, 'U型锁尺寸话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_bicycle', '折叠车便携吗?能带上地铁吗?', '亲,这款车是20寸折叠车,折叠后80x60x40cm可上地铁公交。整车重量12kg手提略重。折叠秒快3秒折叠。Shimano 7速变速上坡省力。建议通勤选折叠车,长途选山地或公路。车架铝合金轻便抗锈。质保3年车架。建议配车袋保护避免刮伤。折叠后可放后备箱。' AS answer, '折叠车,便携,地铁,20寸,Shimano' AS tags, '折叠车便携话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_bicycle', '山地车轮胎多大?防滑吗?', '亲,这款车配26x1.95山地胎,齿纹深防滑抓地力好适合越野。建议城市通勤换光头胎更省力。雨天减速避免侧滑。轮胎规格请参考原车。建议选正新、建大等品牌。建议定期检查胎压30到50psi。外胎磨损及时换避免爆胎。质保3年车架1年轮胎。建议备胎必备。' AS answer, '山地车,轮胎,26寸,防滑,齿纹' AS tags, '山地车轮胎话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车尺码怎么选?我180cm适合多大?', '亲,180cm建议选54cm车架。尺码表:50cm适合165到175cm,54cm适合175到185cm,58cm适合185到195cm。建议试骑更准。这款车是铝合金车架轻便抗锈。Shimano Claris 16速变速。轮组700C标准公路车。整车重量11kg。建议按身高选尺码,腿长略短选小一码。质保3年车架。' AS answer, '公路车,尺码,180cm,54cm,铝合金' AS tags, '公路车尺码话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车上牌需要什么?需要驾照吗?', '亲,电动自行车上牌需合格证、发票、身份证,到交警队办理。新国标电动自行车无需驾照,电动摩托车需E证。请确认当地政策。这款车符合新国标最高时速25km/h无需驾照。建议上牌后上路,配头盔。电池48V20Ah续航60到80公里。质保3年车架1年电池。提供正规发票。' AS answer, '电动车,上牌,驾照,新国标,合格证' AS tags, '电动车上牌话术' AS source_summary, 88 AS score
  UNION ALL SELECT 'auto_bicycle', '密码锁安全吗?忘记密码怎么办?', '亲,密码锁5位密码10万种组合,相比钥匙锁更方便无需带钥匙。建议设复杂密码避免被猜。忘记密码可重置或联系客服。这款是5位密码锁锌合金材质。建议选U型密码锁更安全。质保1年。建议同时配U型锁双锁更安全。锁车架和固定物避免搬运。建议买保险更保障。' AS answer, '密码锁,5位,安全,重置,锌合金' AS tags, '密码锁话术' AS source_summary, 80 AS score
  UNION ALL SELECT 'auto_bicycle', '儿童自行车多大适合5岁孩子?带辅助轮吗?', '亲,5岁孩子建议选16寸儿童车。尺码表:14寸3到5岁,16寸4到7岁,18寸6到9岁,20寸8到12岁。这款车配辅助轮可拆卸,适合初学。车架钢制坚固耐用。建议选轻便款孩子骑不累。建议配头盔护具保护安全。质保1年。建议根据孩子身高选尺码,腿能着地为宜。' AS answer, '儿童车,16寸,5岁,辅助轮,头盔' AS tags, '儿童自行车话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', '山地车怎么保养?链条上油吗?', '亲,山地车保养:链条每月上油一次用专用链条油。刹车片磨损及时换。轮胎胎压30到50psi。螺丝定期检查紧固。建议定期洗车保持干净。这款车是铝合金车架抗锈。Shimano 21速变速。机械碟刹。质保3年车架1年零件。建议保留保养记录质保有效。我们提供保养手册。' AS answer, '山地车,保养,链条,上油,胎压' AS tags, '山地车保养话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车保养和山地车有什么不同?', '亲,公路车保养比山地车简单,路面平磨损少。链条每月上油。刹车片磨损及时换。胎压80到120psi每周打气。轮胎细易扎钉建议备胎。这款车是700C细胎低阻力。铝合金车架轻便抗锈。Shimano Claris 16速变速。质保3年车架1年零件。建议定期检查外胎磨损避免爆胎。' AS answer, '公路车,保养,山地车,链条,胎压' AS tags, '公路车保养话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车能改装增加续航吗?合法吗?', '亲,电动车改装电池增加续航属于非法改装,上路被查罚款扣车。建议选大容量电池款合规升级。这款车48V20Ah续航60到80公里满足日常。电池可拆卸室内充电。新国标最高时速25km/h。建议上牌后上路。质保3年车架1年电池。提供正规发票协助上牌。建议买保险更保障。' AS answer, '电动车,改装,续航,非法,新国标' AS tags, '电动车改装话术' AS source_summary, 87 AS score
  UNION ALL SELECT 'auto_bicycle', '链条锁能防液压剪吗?多粗合适?', '亲,链条锁建议选10mm以上锰钢材质,防液压剪防锯。这款车是12mm锰钢链条锁,外裹尼龙套防刮车。建议选带防尘罩锁芯更耐用。链条锁灵活可锁固定物但比U型锁重。建议U型锁加链条锁双锁更安全。质保5年。建议锁车架和固定物避免搬运。建议买保险更保障。' AS answer, '链条锁,液压剪,锰钢,12mm,尼龙套' AS tags, '链条锁话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', '死飞车能上路吗?没有刹车安全吗?', '亲,死飞车没有刹车不允许上路,属于场地车或场地表演用。建议选带前后刹车的公路车或城市车更安全。死飞车技巧性强新手不建议。建议选符合国标的自行车有刹车有反光片。这款车是城市通勤车前后V刹制动可靠。质保3年车架。建议配头盔保护安全。建议买保险更保障。' AS answer, '死飞车,刹车,上路,安全,国标' AS tags, '死飞车话术' AS source_summary, 86 AS score
  UNION ALL SELECT 'auto_bicycle', '山地车座椅不舒服能换吗?有软座吗?', '亲,山地车座椅可以换,建议选硅胶软座或凹槽透气款更舒适。这款车配专业骑行座,建议穿骑行裤更舒服。座垫高度可调,建议腿伸直微弯最佳。座椅快拆设计方便调节。建议长途选凝胶款减震好。质保1年座椅。建议根据骑行习惯选座垫。我们提供多种座垫可选。' AS answer, '山地车,座椅,硅胶,软座,骑行裤' AS tags, '山地车座椅话术' AS source_summary, 82 AS score
  UNION ALL SELECT 'auto_bicycle', '公路车踏板是自锁吗?需要锁鞋吗?', '亲,这款车配平踏板,自锁踏板需另购约200元,需配锁鞋。自锁踏板效率高但新手需练习解锁避免摔倒。建议入门选平踏板,进阶升级自锁。建议选带钉踏板防滑。踏板规格请参考原车。质保1年踏板。建议配骑行鞋更安全。我们提供多种踏板可选。建议根据骑行习惯选踏板。' AS answer, '公路车,踏板,自锁,锁鞋,平踏板' AS tags, '公路车踏板话术' AS source_summary, 84 AS score
  UNION ALL SELECT 'auto_bicycle', '电动车雨衣有吗?下雨天能骑吗?', '亲,电动车雨天可以骑但建议减速慢行。建议配雨衣雨罩保护。这款车配挡风板雨天挡水。建议选分体雨衣更灵活。雨天刹车距离长提前刹车。建议轮胎选防滑款。电池防水设计雨天可用。质保3年车架1年电池。建议大雨避免骑行安全第一。我们提供雨衣雨罩可选。' AS answer, '电动车,雨衣,雨天,防滑,挡风板' AS tags, '电动车雨衣话术' AS source_summary, 83 AS score
  UNION ALL SELECT 'auto_bicycle', '指纹锁安全吗?能存几个指纹?', '亲,指纹锁采用半导体指纹识别,比光学识别更安全防假指纹。可存10组指纹家人共用。USB充电续航6个月。防水IP65雨天可用。建议选带报警款威慑小偷。这款是指纹U型锁锰钢材质防液压剪。质保1年。建议同时配机械锁双锁更安全。锁车架和固定物避免搬运。' AS answer, '指纹锁,半导体,10组,USB,IP65' AS tags, '指纹锁话术' AS source_summary, 85 AS score
  UNION ALL SELECT 'auto_bicycle', '自行车配件有哪些必备?新手怎么选?', '亲,自行车必备配件:头盔、车灯、车锁、打气筒、补胎工具、备胎。建议选带认证头盔保命。车灯选USB充电款。车锁选U型锁更安全。打气筒带气压表。补胎工具包便携。建议配骑行手套和骑行裤更舒适。这款车配基础工具包。质保3年车架。建议根据骑行需求选配。' AS answer, '自行车,配件,头盔,车灯,车锁' AS tags, '自行车配件话术' AS source_summary, 86 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;
