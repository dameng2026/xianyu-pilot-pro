-- ============================================================
-- V1.50: 交易通用问题类种子Q&A（6个二级分类 × 30条 = 180条）
-- 一级分类: 交易通用问题 (general_trade)
-- 二级分类:
--   general_stock_query     库存查询（30条）
--   general_shipping_track  发货跟踪（30条）
--   general_refund_aftersale 退款售后（30条）
--   general_product_consult 商品咨询（30条）
--   general_price_discount  价格优惠（30条）
--   general_account_login   账号登录（30条）
-- 风格: 销冠级话术，应对刁钻问题，自然口语化，不机械化
-- 覆盖场景: 咨询、催促、抱怨、砍价、售后、纠纷
-- source_type='seed' 标记为人工种子Q&A，与 ai 自动学习区分
-- 评分范围: 70-95，按问题价值与回复质量差异化分配
-- 敏感词已过滤: 不含手机号、微信号、外部联系方式
-- ============================================================

-- ============ 库存查询 general_stock_query（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_stock_query' AS code, '在不在？还有货吗？' AS question, '亲，在的，现货库存充足，下单后24小时内安排发出。您这边需要什么颜色或规格的呢？我帮您确认下库存' AS answer, '库存,有货,现货,响应' AS tags, '有货时的快速响应话术' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_stock_query', '这个还有吗？怕下单了没货白等', '亲放心，目前还有库存的，我看您是真心想买，要不现在就给您留着？您下单后我今天就给您发出去，绝不耽误', '库存,保留,催单,安抚' AS tags, '安抚买家担心断货并促成下单' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_stock_query', '没货了为什么不早点说？浪费我时间', '亲真的很抱歉，刚系统显示还有1件的，但仓库核实发现已被预定了，这是我的失误。我给您申请了10元优惠券作为补偿，您看是想要同款其他颜色还是等下一批到货？我帮您优先预留', '缺货,道歉,补偿,危机处理' AS tags, '缺货时的道歉补偿与替代方案' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_stock_query', '能不能拍下来囤着？我下个月用', '亲可以的，但建议您需要的时候再下单哦，因为我们家商品都是新鲜批次发货，囤久了可能影响使用体验。如果您确定要囤，我帮您备注优先发新批次，您看行吗', '库存,囤货,建议,新鲜批次' AS tags, '避免囤货风险并给出专业建议' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_stock_query', '你们家库存还有多少？我想多买几件', '亲，目前库存还有不少，您想买几件呢？我帮您算下邮费，量大还能给您优惠点。如果是同城还可以面交省运费，您看怎么方便', '库存,批量,优惠,邮费' AS tags, '批量购买引导并给出优惠预期' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_stock_query', '我看显示还有2件，是真的吗？别拍了说没货', '亲，库存显示是实时的，但偶尔会有几分钟延迟。您看中的话建议尽快下单哦，毕竟这价格挺划算的，前几天刚卖了3件，手慢就没了', '库存,实时,催单,准确性' AS tags, '库存准确性确认并引导尽快下单' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_stock_query', '还有别的颜色吗？这个颜色不太想要', '亲，我们家还有黑色、白色、蓝色三种颜色可选，您看下哪种合适？不同颜色库存不一样，我帮您查下哪个颜色现货最快发出', '库存,颜色,选择,查询' AS tags, '颜色选择引导并主动查询库存' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_stock_query', '断货了什么时候补？能等到吗', '亲，这批断货后预计下周三能补到货，我可以帮您预留一件，到货后第一时间通知您发货。现在下单还能享受现在的价格哦，补货后可能调价', '断货,补货,预留,价格' AS tags, '断货应对策略并引导提前锁价' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_stock_query', '你们家是不是搞饥饿营销？故意说没货', '亲，我们绝不会饥饿营销的，闲鱼本来就不是大平台，我们做的是口碑生意，确实是因为这款太好卖了才断货的。您要不看下我们家其他款？有几款性价比比这个还高，我发您参考下', '库存,质疑,信任,替代推荐' AS tags, '化解饥饿营销质疑并推荐替代款' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_stock_query', '现在下单什么时候能到手上？', '亲，今天17点前下单今天就能发出，江浙沪一般2天到，其他地区3到5天到。如果您急用，我可以帮您改顺丰到付，时效更快，您看需要吗', '库存,发货时效,顺丰,催单' AS tags, '发货时效承诺并提供加急选项' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_stock_query', '库存准不准啊？我怕拍了又给我取消订单', '亲，我们的库存是和仓库实时同步的，准确率很高。万一真的出现超卖情况，我会第一时间通知您并全额退款，还会额外补偿您一张优惠券，绝不让您白等', '库存,准确性,超卖,补偿' AS tags, '库存准确性承诺并兜底超卖风险' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_stock_query', '能不能帮我留着？我明天再付款', '亲，闲鱼系统是拍下减库存的，您可以先拍下不付款，我帮您保留24小时。超过24小时系统会自动关闭订单哦，您看这样可以吗', '库存,保留,拍下不付款,时效' AS tags, '保留库存方案与系统规则说明' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_stock_query', '所有尺码都有货吗？别我拍了某个码说没有', '亲，我帮您逐一核实下尺码库存。您告诉我想要哪个码，我马上查仓库。大部分尺码都有货，个别热门码可能库存不多了，您报码我帮您确认最准', '库存,尺码,查询,核实' AS tags, '尺码库存逐一核实避免错单' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_stock_query', '这款还会不会停产？我还想再等等看', '亲，这款目前没有停产计划，但厂家说不准什么时候调整生产线。如果您真心喜欢，建议趁现在有货先拿下，停产后再找就难了，价格也可能涨。您看要不要先拍', '库存,停产,建议,催单' AS tags, '停产咨询回应并引导趁早下单' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_stock_query', '你们家是不是真假混卖？库存里会不会掺了假货', '亲，我们只做正品，每一件都是自己验过的，支持专柜验货和得物鉴定，假一赔十。做长久生意的人不会真假混卖砸自己招牌的，您放心拍', '库存,真假,正品,验货,信任' AS tags, '化解真假混卖质疑并承诺验货' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_stock_query', '能不能预定？等补货了第一个发给我', '亲，可以的，您先拍下付款，我帮您备注预定订单，补货到仓后第一个给您发出。预计下周三到货，到货后我立刻通知您，您看行吗', '库存,预定,补货,优先发货' AS tags, '预定机制说明并给出到货预期' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_stock_query', '我看别人家比你便宜，你库存还有吗？', '亲，库存还有的。价格方面，我们家保证正品行货，支持验货，品质有保障。便宜的可能成色或版本不一样，您对比下细节图就知道了。您要是诚心要，我也给您优惠点', '库存,价格对比,正品,优惠' AS tags, '应对价格对比并强调品质差异' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_stock_query', '现货还是预售？说不清楚我不拍', '亲，这款是现货，仓库有库存的，下单后24小时内发出，不是预售。您放心拍，有任何问题我兜底', '库存,现货,预售,澄清' AS tags, '现货预售澄清打消下单顾虑' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_stock_query', '库存怎么一直在变？刚才还3件现在1件了', '亲，库存是实时变动的，因为有其他买家也在看也在下单。刚才3件可能已经被人拍走2件了，您看中的话建议尽快下手，晚了可能就没了', '库存,动态,催单,实时' AS tags, '库存变动解释并制造紧迫感' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_stock_query', '能不能多买几个？我帮朋友也带一份', '亲，当然可以，多买我还能给您算个优惠价。您要几件？我帮您查下库存够不够，够的话直接发一个包裹省运费，您看行吗', '库存,多买,优惠,合并发货' AS tags, '批量购买引导并给出合并发货方案' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_stock_query', '有没有配套的XX？我想一起买了', '亲，有的，配套的XX也有现货，您要一起买的话我给您算个套装价，比单买划算。我发您套装链接，您看下满意就一起拍', '库存,配套,套装,关联推荐' AS tags, '关联推荐促成套装购买' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_stock_query', '这款还会补货吗？还是卖完就没了？', '亲，这款是常规款，会持续补货的，但每次到货数量不多，可能要等一两周。如果您急用建议趁现在有货先拍，不急的话也可以等下一批，我帮您留意', '库存,补货,常规款,建议' AS tags, '补货计划说明并给出购买建议' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_stock_query', '我上次来还有货，怎么现在没了？', '亲，实在抱歉，这款确实卖得比较快，上次您看的时候还有，这几天就卖完了。不过下周三会到新货，我帮您预留一件，到货第一时间通知您，您看可以吗', '库存,缺货,道歉,预留' AS tags, '缺货道歉并主动预留补货' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_stock_query', '能不能先拍下不付款？等有货了再付', '亲，可以先拍下不付款，系统会帮您保留库存24小时。但超过24小时不付款订单会自动关闭，库存就释放了。您确定要的话建议尽快付款，免得被别人抢了', '库存,拍下不付款,保留,时效' AS tags, '拍下不付款规则说明与时效提醒' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_stock_query', '库存显示0但还能下单是什么意思？', '亲，这种情况可能是系统延迟，实际可能已经没货了。您先别急着付款，我帮您去仓库核实下，如果有货马上通知您付款发货，如果真没货了就不耽误您时间了', '库存,异常,核实,延迟' AS tags, '库存显示异常的核实处理流程' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_stock_query', '你们仓库在哪？能不能自己去拿？省个邮费', '亲，仓库在XX市，支持同城自提的，您方便过来的话可以当面验货再拿走，省运费也更放心。您看什么时候方便来？我帮您约个时间', '库存,仓库,自提,同城' AS tags, '同城自提方案并引导当面验货' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_stock_query', '这个颜色没货了，其他颜色有吗？一样吗', '亲，这个颜色确实暂时没货了，但其他颜色都有现货。不同颜色只是外观区别，质量和功能完全一样。您看下这几个颜色哪个顺眼，我帮您查下库存', '库存,颜色,切换,查询' AS tags, '缺货颜色切换并引导选择替代色' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_stock_query', '能不能帮我查下XX型号还有没有？', '亲，可以的，您把型号发我，我帮您去仓库查。不过仓库盘点需要点时间，您稍等几分钟，查到后第一时间告诉您结果', '库存,型号,查询,仓库' AS tags, '型号库存查询并管理等待预期' AS source_summary, 81 AS score
  UNION ALL SELECT 'general_stock_query', '什么时候补货？能不能到货了通知我？', '亲，预计下周三补到货，我帮您备注到货通知，货一到我立刻发消息给您。您也可以先拍下锁价格，补货后第一时间给您发，不用等通知', '库存,补货,到货通知,锁价' AS tags, '到货通知服务并引导提前锁价' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_stock_query', '库存够吗？我怕拍多了你们发不出来', '亲，您要几件？我先帮您确认下库存量。如果库存不够我会如实告诉您，不会接了单发不出货。一般小批量都没问题的，您报个数我马上查', '库存,充足,批量,如实' AS tags, '库存充足确认并承诺如实告知' AS source_summary, 82 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 发货跟踪 general_shipping_track（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_shipping_track' AS code, '什么时候发货？我等着用呢' AS question, '亲，今天17点前下单今天发，17点后下单明天上午发。正常江浙沪2天到货，其他地区3到5天到。急用的话可以备注顺丰到付，时效更快' AS answer, '发货,时效,顺丰,催单' AS tags, '发货时效标准回答并提供加急选项' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_shipping_track', '我下单好久了怎么还没发货？是不是忘了', '亲，我帮您查下订单状态，您稍等。如果是今天下的单会在17点前发出；如果昨天下的还没发货，可能是仓库漏单了，我马上帮您催一下，今天一定给您发出去，给您添麻烦了', '发货,延迟,催单,道歉' AS tags, '延迟发货排查处理与道歉' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_shipping_track', '快递单号多少？我要查物流', '亲，刚给您发货了，单号我已经填到订单里了，您在闲鱼订单详情里就能看到。物流信息一般2到4小时更新，您可以去快递官网查实时轨迹，有问题随时找我', '快递单号,物流,查询' AS tags, '快递单号提供并引导自助查询' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_shipping_track', '物流显示在XX中转站停了3天了，是不是丢了？', '亲，您别急，有时候中转站爆仓会导致物流停滞，我这边帮您联系快递公司催一下。如果3天后还没动静，我直接帮您申请赔付或者重新补发，您看可以吗？绝对不让您吃亏', '物流,停滞,丢件,赔付,补发' AS tags, '物流停滞处理与赔付补发兜底' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能改地址？我刚才填错了', '亲，如果还没发货可以直接改，您把新地址发我，我帮您备注。如果已经发货了，我帮您联系快递拦截改地址，但拦截不一定成功，如果拦截失败需要您到时拒收，我们重新发，您看行吗', '改地址,拦截,拒收,重发' AS tags, '改地址处理流程与兜底方案' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_shipping_track', '为什么还不揽收？我看物流没更新', '亲，今天发出的件快递小哥一般在下午5到8点来揽收，揽收后扫描才会有物流更新。您再等等，明天早上应该就能看到揽收记录了。如果明天还没更新，我帮您催快递', '揽收,物流更新,时效' AS tags, '揽收延迟解释并给出更新预期' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能改顺丰？我急用', '亲，可以改顺丰的，顺丰到付需要您补差价，一般15到20元左右。您下单后备注一下改顺丰到付，我帮您改快递。也可以补差价发顺丰现付，您看哪种方便', '顺丰,加急,差价,改快递' AS tags, '改顺丰方案与差价说明' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_shipping_track', '快递到了但我没收到，显示已签收了', '亲，我帮您查一下，可能是快递员放到菜鸟驿站或者快递柜了，您看下有没有取件码。如果没收到，可能是代签收或送错了，我立刻联系快递员核实，今天帮您解决', '已签收,未收到,驿站,核实' AS tags, '虚假签收排查与跟进处理' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_shipping_track', '包装会不会破损？我之前买别家都破了', '亲，我们家包装很用心的，外层加厚纸箱加气泡膜，里面还有防震填充，不会破的。您放心下单，万一真的破损了，您拍照发我，我们包退换，邮费我出', '包装,破损,防震,退换' AS tags, '包装承诺并兜底破损退换' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_shipping_track', '包邮吗？运费多少？', '亲，这款默认包邮的，江浙沪皖首重包邮，偏远地区可能需要补差价。您报下收货地址，我帮您确认下运费，如果需要补差价我会提前告诉您', '包邮,运费,偏远地区' AS tags, '运费说明与偏远地区差价确认' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_shipping_track', '发什么快递？能不能指定', '亲，默认发中通或圆通，如果您有指定快递可以备注，我尽量满足。部分快递偏远地区可能到不了，您报下地址我帮您查哪种快递能到，确保给您发到', '快递,指定,偏远,查询' AS tags, '快递选择说明并满足指定需求' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_shipping_track', '今天能发吗？我后天就要用', '亲，今天17点前下单今天就能发，走顺丰的话后天之前应该能到。您要不要改顺丰到付？我帮您备注加急，尽量赶在您用之前送到', '发货,当天,顺丰,加急' AS tags, '当天发货承诺并提供加急方案' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_shipping_track', '能加急吗？越快越好', '亲，可以加急的，最快是顺丰即日达或次晨达，但要看您所在城市是否覆盖。您报下收货城市，我帮您查顺丰最快的时效，确认后帮您改单', '加急,顺丰,时效,查询' AS tags, '加急方案与顺丰时效查询' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_shipping_track', '同城能自提吗？我就在你们附近', '亲，支持同城自提的，您方便过来的话可以当面验货再拿走，省运费也更放心。您看什么时候方便来？我帮您约个时间，把货准备好等您', '同城,自提,验货,省运费' AS tags, '同城自提引导并约定取货时间' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_shipping_track', '节假日发货吗？周末能不能发', '亲，周末和节假日正常发货的，快递公司节假日也揽收，只是派送可能延迟1到2天。您放心下单，我们不会因为节假日耽误发货的', '节假日,发货,周末,延迟' AS tags, '节假日发货说明与时效预期' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_shipping_track', '物流显示退回去了怎么回事？', '亲，可能是地址不详、电话打不通或者超区派送不了导致退回。我帮您联系快递查具体原因，如果是地址问题我们改地址重新发，如果是快递原因我帮您投诉并补发，不让您承担', '物流,退回,查原因,补发' AS tags, '快递退回原因排查与补发处理' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_shipping_track', '能发到XX地区吗？会不会到不了', '亲，您报下具体地址，我帮您查快递能不能到。一般偏远地区可能需要转其他快递或者补偏远邮费。如果实在到不了，我可以帮您发EMS，全国都能到，就是时效慢一点', '偏远地区,EMS,查询,转快递' AS tags, '偏远地区发货方案与EMS兜底' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_shipping_track', '快递能不能放驿站？我不在家', '亲，可以的，您下单时备注放驿站或快递柜就行。我帮您在包裹上也贴个备注条，快递员看到会放驿站的。您回来凭取件码取就行，很方便', '驿站,快递柜,备注,代收' AS tags, '驿站代收方案与备注处理' AS source_summary, 81 AS score
  UNION ALL SELECT 'general_shipping_track', '发货前能帮我检查一下吗？别发个坏的', '亲，当然可以，发货前我们每件都会检查的，确认无瑕疵无破损才发出。您有什么特别要检查的也可以告诉我，我帮您一一确认，拍发货前照片给您看', '发货,检查,质检,拍照' AS tags, '发货前质检承诺并提供拍照确认' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能指定发XX快递？我那边只有这个快递', '亲，可以的，您指定快递我帮您发。不过部分快递某些地区可能不到，您确认下您那边XX快递能不能到，能到的话我帮您发这个快递', '快递,指定,查询' AS tags, '指定快递满足与到货确认' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_shipping_track', '物流一直不更新怎么办？是不是出问题了', '亲，物流超过24小时没更新可能是揽收延迟或中转站爆仓。我帮您联系快递催一下，一般催完24小时内会有更新。如果超过3天还没动，我帮您申请遗失处理并补发，您放心', '物流,不更新,催快递,补发' AS tags, '物流停滞处理与遗失补发兜底' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能晚几天发？我下周才在家', '亲，可以的，您下单后告诉我希望哪天发，我帮您备注延迟发货，到时间再发出。不过库存先帮您锁住，您放心，不会因为晚发就没货了', '延迟发货,备注,锁库存' AS tags, '延迟发货方案与库存锁定承诺' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_shipping_track', '发货了会通知我吗？', '亲，会的，发货后系统会自动推送消息给您，快递单号也会同步到订单里。您留意下消息通知就行，也可以随时来问我物流单号', '发货,通知,单号,消息' AS tags, '发货通知说明与单号同步' AS source_summary, 78 AS score
  UNION ALL SELECT 'general_shipping_track', '快递到付还是现付？运费怎么算', '亲，默认包邮现付的，您不用额外付运费。如果改顺丰到付，快递费您收货时付给快递员。您看是走包邮快递还是改顺丰到付', '运费,到付,现付,包邮' AS tags, '运费支付方式说明与选择引导' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_shipping_track', '包裹多重？运费会不会很贵', '亲，包裹大约X公斤，首重内包邮的，不超重就不用补运费。如果偏远地区可能需要补偏远邮费，我提前帮您查好告诉您，不会让您多花冤枉钱', '重量,运费,包邮,偏远' AS tags, '包裹重量与运费说明' AS source_summary, 79 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能拆开发货？我买给两个人的', '亲，可以拆发的，您下单后告诉我分两个地址，我帮您拆成两个包裹分别发出。邮费的话首重内各算一次，您补一个首重运费就行，我帮您算好', '拆发,多地址,运费' AS tags, '拆分发货方案与运费计算' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_shipping_track', '发货地址能不能写公司？我白天都在公司', '亲，可以的，您下单时填公司地址就行，备注白天派送。我帮您在包裹上也备注一下，快递员白天送到公司前台。您确认下公司地址和上班时间，我帮您备注好', '发货,公司地址,白天派送' AS tags, '公司地址发货与白天派送备注' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_shipping_track', '物流显示派送中但快递员电话打不通', '亲，我帮您联系快递站点催一下，让站点通知快递员尽快联系您。如果今天联系不上，我帮您要求站点改派或者自提，绝不让您干等着', '派送,联系不上,催站点' AS tags, '派送异常处理与站点协调' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_shipping_track', '能不能保价？东西挺贵的我不放心', '亲，可以保价的，您下单时备注需要保价，我帮您申请保价服务，保价费按声明价值的千分之几收取。贵重物品建议保价，这样运输途中万一有问题也能全额赔付', '保价,贵重,赔付,运输' AS tags, '保价服务说明与贵重物品建议' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_shipping_track', '发货时效保不保证？超时了怎么办', '亲，我承诺24小时内发货，正常3到5天到货。如果超过7天还没到，我帮您查物流原因，确认遗失的话立刻补发并走赔付流程，不会让您一直等', '时效,保证,超时,补发' AS tags, '发货时效承诺与超时兜底方案' AS source_summary, 87 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 退款售后 general_refund_aftersale（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_refund_aftersale' AS code, '收到货坏了，你们怎么包的' AS question, '亲，实在抱歉！可能是运输途中暴力分拣导致的。您拍几张破损照片发我，我马上帮您处理，可以选择补发或者全额退款，邮费我全包，绝不让您吃亏' AS answer, '破损,道歉,补发,退款,邮费' AS tags, '收到破损商品的道歉与补发退款方案' AS source_summary, 93 AS score
  UNION ALL SELECT 'general_refund_aftersale', '收到货跟描述完全不符，坑人啊', '亲，非常抱歉给您带来不好的体验。能具体说下哪里和描述不符吗？如果确实是我们描述有误，我承担全部责任，退款退货邮费我出。您拍个对比图发我，我看看怎么处理最好', '描述不符,道歉,退款,邮费,责任' AS tags, '描述不符的道歉与责任承担' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_refund_aftersale', '我不想要了，能退款吗', '亲，可以的，商品不影响二次销售的情况下支持7天无理由退货。您在订单里申请退款，把商品寄回来，我收到后确认无误立刻给您退款。退回运费需要您自己承担哦', '退款,7天无理由,退货,运费' AS tags, '无理由退款流程与运费说明' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_refund_aftersale', '能换货吗？尺码不合适', '亲，可以换货的，您把商品寄回来，我帮您换合适的尺码。换货邮费各付一趟，您寄过来的运费您出，我重新发给您的运费我出。您报下要换的尺码，我帮您确认有没有货', '换货,尺码,邮费,确认库存' AS tags, '换货流程与邮费分担说明' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_refund_aftersale', '有保修吗？坏了找谁修', '亲，这款保修3个月，非人为损坏免费维修。如果是人为损坏可以付费维修，只收配件成本费。有问题随时找我，我帮您安排售后，不会找不到人的', '保修,维修,非人为,售后' AS tags, '保修政策说明与售后渠道' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_refund_aftersale', '质量问题退货运费谁出？凭什么我出', '亲，如果是质量问题，退货运费由我们承担，您先垫付，收到退货后我把运费转给您。您拍照保留一下质量问题的证据，方便我们核实和处理，绝不让您多花一分钱', '质量问题,运费,垫付,赔偿' AS tags, '质量问题运费承担与垫付流程' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_refund_aftersale', '支持7天无理由吗？有什么条件', '亲，支持7天无理由退货的。条件是商品不影响二次销售，吊牌未剪、未使用、包装完整。您收到后如果不满意，7天内申请退货就行，退回运费您自理', '7天无理由,条件,二次销售,运费' AS tags, '7天无理由退货条件说明' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_refund_aftersale', '我用了一次还能退吗？实在不满意', '亲，用过的话会影响二次销售，按规定是不太好转的。不过您能说下具体哪里不满意吗？如果是质量问题我肯定给您退，如果是个人喜好原因，我帮您和仓库商量下看能不能通融', '用过,退货,二次销售,通融' AS tags, '使用后退换的规则说明与协商' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_refund_aftersale', '包装拆了还能退吗？我只是看了一下', '亲，包装拆了但商品没使用、不影响二次销售的话是可以退的。您把原包装留好，商品和配件都齐全，7天内申请退货就行。退回运费您自理哦', '拆封,退货,包装,二次销售' AS tags, '拆封后退换条件说明' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_refund_aftersale', '退款多久到账？我急用钱', '亲，我收到退货确认无误后立刻同意退款，退款一般1到3个工作日原路退回。如果是退款到支付宝通常当天到，银行卡可能需要1到2天，您留意下到账通知', '退款,到账,时效,原路' AS tags, '退款到账时效与原路退回说明' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_refund_aftersale', '收到货少件了，里面少了个配件', '亲，实在抱歉，可能是仓库打包漏放了。您拍个收到的照片发我，我核实后立刻帮您补发配件，今天就能发出，不用您退回。给您添麻烦了', '少件,漏发,补发,道歉' AS tags, '漏发配件的道歉与补发处理' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_refund_aftersale', '发错货了！我拍的A你发了B', '亲，非常抱歉，仓库打包搞错了。您把收到的商品拍个照片发我，我核实后立刻帮您重新发正确的货，错发的您寄回来，运费我全包。今天就能给您补发', '错发,道歉,补发,运费' AS tags, '错发商品的道歉与补发流程' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_refund_aftersale', '质量有问题但过了7天了，还能退吗', '亲，7天无理由是过期了，但如果是质量问题，我们提供3个月保修。您拍个质量问题的照片发我，我帮您判断是维修还是换新。非人为损坏免费修，不会让您掏冤枉钱', '过保,质量问题,保修,维修' AS tags, '过7天质量问题的保修处理' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_refund_aftersale', '能不能只退一部分？有几个配件我不需要', '亲，这个需要看具体情况，如果配件是独立包装的可以部分退。您说下要退哪些，我帮您算下差价，退回的配件不影响二次销售就行。您先把要退的拍个照片发我确认下', '部分退款,配件,差价,确认' AS tags, '部分退款方案与差价计算' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_refund_aftersale', '退款流程怎么走？我没退过不知道', '亲，很简单，您在闲鱼订单里点申请退款，选择退款原因，我这边同意后您把商品寄回来。我收到退货确认没问题就同意退款，钱原路退回给您。整个过程一般3到5天，我随时帮您跟进', '退款,流程,引导,跟进' AS tags, '退款流程分步引导与跟进承诺' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_refund_aftersale', '收到货跟图片差太多了，这明明不是同一个东西', '亲，非常抱歉给您造成这种感觉。您能拍个收到的实物照片发我吗？我对比一下，如果确实和图片差异较大，我承担全部责任，退款退货邮费我出，绝不推诿', '货不对板,道歉,退款,责任' AS tags, '货不对板的道歉与全额退款' AS source_summary, 91 AS score
  UNION ALL SELECT 'general_refund_aftersale', '有质量问题你们包退吗？别到时候扯皮', '亲，质量问题我们一定包退的，邮费也由我们承担。您收到后如果有质量问题，拍照发我，我核实后立刻同意退款退货，绝不扯皮。我们做口碑生意，不会为一单砸招牌', '质量,包退,邮费,承诺,口碑' AS tags, '质量问题包退承诺与口碑背书' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_refund_aftersale', '换货要等多久？我等着用呢', '亲，您把商品寄回来，我收到后当天就帮您重新发货，一般2到3天您就能收到换的货。如果您急用，我可以先帮您发新的，您同时把旧的寄回来，这样不耽误您', '换货,时效,先发后收' AS tags, '换货时效承诺与先发后收方案' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_refund_aftersale', '有没有运费险？退货不想出邮费', '亲，这款暂时没有赠送运费险。不过如果是质量问题退货，邮费由我们承担，您不用出。如果是7天无理由退货，退回运费需要您自理。您也可以自己在下单时购买运费险', '运费险,质量退货,无理由,运费' AS tags, '运费险说明与退货运费规则' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_refund_aftersale', '退款退到哪里？是原路退回吗', '亲，是的，退款是原路退回的。您用什么支付的就退到哪里，支付宝支付退到支付宝，银行卡支付退到银行卡。一般1到3个工作日到账，您留意下到账通知', '退款,原路,到账,时效' AS tags, '退款去向与原路退回说明' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_refund_aftersale', '收到的是假货！你们卖假货', '亲，我们只做正品，支持专柜验货和得物鉴定。如果您怀疑是假货，可以去鉴定，鉴定结果如果是假货，我假一赔十并承担鉴定费和邮费。请您先鉴定确认，我绝不逃避责任', '假货,鉴定,假一赔十,责任' AS tags, '假货质疑的鉴定引导与赔付承诺' AS source_summary, 93 AS score
  UNION ALL SELECT 'general_refund_aftersale', '配件丢了能不能补发？我弄丢了一个小配件', '亲，可以补发的，您告诉我是哪个配件丢了，我帮您查下有没有库存。有的话我帮您寄过去，小配件的话不收您费用，算是我们的小小心意，给您添麻烦了', '配件,丢失,补发,免费' AS tags, '配件丢失的免费补发处理' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_refund_aftersale', '售后找谁？别到时候找不到人', '亲，售后直接找我就行，我是您的专属客服，从售前到售后都负责。您有任何问题随时发消息给我，我看到第一时间回复。不会出现卖了就找不到人的情况，您放心', '售后,专属客服,回复,承诺' AS tags, '售后渠道说明与专属服务承诺' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_refund_aftersale', '商品有划痕但不是运输造成的，发货前就有', '亲，非常抱歉，这可能是发货前质检漏检了。您拍照发我，我核实后帮您处理，可以补发全新或者部分退款补偿，您看怎么处理满意。这是我们的失误，一定给您满意方案', '划痕,漏检,道歉,补发,补偿' AS tags, '发货前瑕疵漏检的道歉与处理' AS source_summary, 89 AS score
  UNION ALL SELECT 'general_refund_aftersale', '退款被拒了怎么办？你们是不是不想退', '亲，退款被拒可能是因为退款原因选的不对或者缺少照片证据。您看下拒绝原因是什么，如果是原因选错我帮您改，如果是缺照片您补传一下。我这边不会故意拒绝的，您放心', '退款,被拒,原因,协助' AS tags, '退款被拒原因排查与协助处理' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_refund_aftersale', '能不能延长收货时间？我怕还没收到就自动确认了', '亲，可以的，您在订单里点延长收货就行，每次可以延长3天。如果物流确实慢，您延长一下就行，不会自动确认的。我也帮您盯着物流，有问题随时通知您', '延长收货,自动确认,物流,跟进' AS tags, '延长收货操作引导与物流跟进' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_refund_aftersale', '收到货有异味正常吗？会不会有毒', '亲，新商品有一点轻微气味是正常的，材质本身的味道，通风放一两天就散了。如果是刺鼻异味那就不正常，您拍照发我，我帮您判断。如果不放心可以退换，邮费我出', '异味,正常,通风,退换' AS tags, '异味判断与退换兜底' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_refund_aftersale', '质量问题需要提供什么证据？怎么证明', '亲，您拍几张质量问题的清晰照片或者视频发我就行，拍清楚问题部位。我核实后会立刻处理，不需要您提供其他证明。如果是需要鉴定的质量问题，鉴定费由我们承担', '质量,证据,照片,视频,鉴定' AS tags, '质量问题举证要求与鉴定费用' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_refund_aftersale', '售后响应快不快？别几天不理我', '亲，售后消息我看到第一时间回复，一般几分钟内响应。如果是晚上或者非工作时间可能稍慢，但不会超过2小时。紧急问题您多发几条消息，我优先处理', '售后,响应,时效,承诺' AS tags, '售后响应时效承诺与优先处理' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_refund_aftersale', '能不能开发票？售后需要发票', '亲，可以开具电子发票的，您下单后告诉我发票抬头和税号，我帮您开好发到您邮箱。如果是售后需要，我补开也没问题，您随时找我', '发票,电子发票,抬头,售后' AS tags, '发票开具与售后补开说明' AS source_summary, 78 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 商品咨询 general_product_consult（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_product_consult' AS code, '多大尺寸？能放得下吗' AS question, '亲，这款尺寸是长XX乘宽XX乘高XX厘米，您量一下要放的位置看够不够。我拍了参照物对比图，您看下心里有数，放不下可以退的' AS answer, '尺寸,规格,参照物,退货' AS tags, '尺寸说明并引导对比确认' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_product_consult', '什么材质的？会不会过敏', '亲，这款是XX材质，亲肤无毒，通过安全检测的，敏感肌也能用。有检测报告，您需要的话我发给您看。如果用了过敏可以退换，邮费我出', '材质,过敏,安全,检测,退换' AS tags, '材质说明与过敏退换承诺' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_product_consult', '什么版本？是国行还是港版', '亲，这款是国行版本，全国联保，支持官方售后。港版价格便宜些但不能国内联保，我们只卖国行，品质和售后都有保障。您放心拍', '版本,国行,联保,售后' AS tags, '版本说明与国行联保优势' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '能用于XX场景吗？我买来XX用的', '亲，可以的，这款适用XX场景。我帮您确认下您的具体需求，确保功能匹配。如果买回去发现不适用，7天内可以退换，不影响二次销售就行', '用途,场景,适用,退换' AS tags, '用途适用性确认与退换保障' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_product_consult', '兼容XX吗？我家里有XX设备', '亲，您把设备型号告诉我，我帮您查下兼容性。一般同品牌的都兼容，跨品牌的话需要看接口和协议。如果不确定可以先拍下试试，不兼容我给您退', '兼容,型号,查询,退货' AS tags, '兼容性查询与退货保障' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_product_consult', '有配件吗？包装里都有什么', '亲，包装内含主机、数据线、充电头、说明书、保修卡，配件齐全。您看还需要额外配件吗？我这边有原装配件可以一起买，给您算优惠价', '配件,包装,清单,优惠' AS tags, '配件清单说明与关联销售' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_product_consult', '什么牌子？没听过这个牌子靠谱吗', '亲，这是XX品牌，虽然名气没有大牌那么响，但品质不输大牌，我们卖了好久了，回头客很多。您可以看下评价，买家反馈都很好。支持验货，不满意可退', '品牌,口碑,评价,验货' AS tags, '小众品牌口碑背书与验货承诺' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '哪里生产的？是不是贴牌的', '亲，这款是XX地生产的，原厂出品不是贴牌。有原厂出货单和质检报告，您需要可以发您看。我们做正品生意，不会拿贴牌糊弄人', '产地,贴牌,正品,质检' AS tags, '产地说明与正品背书' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_product_consult', '保质期到什么时候？别快过期了', '亲，这款保质期到2027年12月，还有一年多呢，放心用。我们都是发新鲜批次的，不会发临期的。如果您收到发现临期了，我给您退换', '保质期,新鲜批次,临期,退换' AS tags, '保质期说明与临期退换承诺' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '真伪怎么查？我怕买到假的', '亲，这款支持多种验真方式，可以扫包装上的防伪码查，也可以去专柜验货，或者走得物鉴定。假一赔十，鉴定费我出。您放心拍，正品才敢这么承诺', '真伪,验货,防伪码,假一赔十' AS tags, '真伪验证方式与假一赔十承诺' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_product_consult', '详细参数发一下，我想对比下', '亲，详细参数我发您，包括尺寸、重量、材质、功率、电压等。您看下有没有遗漏的，需要补充的告诉我。对比后有任何疑问随时问我，我帮您解答', '参数,详细,对比,解答' AS tags, '详细参数提供与对比解答' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_product_consult', '有没有实物图？别只发精修图', '亲，有的，我给您拍几张实物无滤镜图和细节图，您看下。实物和精修图可能有轻微色差，但整体是一样的。您放心，收到不满意可以退', '实物图,无滤镜,细节,色差' AS tags, '实物无滤镜图提供与色差说明' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_product_consult', '新的还是二手的？别含糊', '亲，这款是全新的，未拆封未使用，原盒原配件。我拍了包装封条图给您看，收到货一摸就知道是新的。二手我们会在标题和描述里明确标注的，不会含糊', '全新,二手,未拆封,标注' AS tags, '全新确认与二手标注说明' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '有没有瑕疵？别收到才发现', '亲，全新的没有瑕疵，我发货前会逐件检查。如果是二手款，我会把所有使用痕迹如实描述并拍细节图，不会藏着掖着。您收到有任何问题随时找我', '瑕疵,检查,如实,细节图' AS tags, '瑕疵说明与发货前检查承诺' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_product_consult', '适合什么人群用？我买给老人的', '亲，这款操作简单，老人用没问题，我拍了操作演示图您可以看看。如果是给老人用，建议选简单模式的版本，我帮您推荐下。不合适可以退换', '人群,老人,操作,推荐,退换' AS tags, '适用人群判断与操作演示' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_product_consult', '有没有说明书？看不懂怎么办', '亲，有说明书的，包装里附带。如果看不懂可以随时问我，我帮您一步步讲解。也可以发您电子版说明书和操作视频，更直观。您放心，包教包会', '说明书,讲解,视频,教学' AS tags, '说明书提供与教学支持承诺' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_product_consult', '能不能教我怎么用？第一次买不会', '亲，当然可以，我发您一个操作视频，跟着做就行。要是还有不明白的随时问我，我帮您一步步讲解。很简单，几分钟就能学会，您放心', '使用,教学,视频,讲解' AS tags, '使用指导与视频教学' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_product_consult', '和XX款有什么区别？我纠结买哪个', '亲，两款主要区别是XX和XX，XX款适合XX需求，这款适合XX需求。您说下您的使用场景，我帮您推荐更合适的。买错了我给您换，不用担心', '对比,区别,推荐,换货' AS tags, '产品对比分析与场景推荐' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_product_consult', '有没有保修卡？售后凭证', '亲，有的，包装内附带保修卡，凭保修卡享受3个月免费保修。您收货后把保修卡收好，售后时用得上。电子保修记录也可以查，双重保障', '保修卡,凭证,电子保修,保障' AS tags, '保修卡提供与电子保修说明' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_product_consult', '是国行还是水货？水货我不敢要', '亲，这款是国行正品，有官方保修，支持全国联保。水货我们不做的，做国行才长久。您收到可以去官方查序列号验证，假一赔十', '国行,水货,联保,序列号' AS tags, '国行正品说明与序列号验证' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_product_consult', '容量多大？够用吗', '亲，这款容量是XX，日常使用完全够。如果您存储需求大可以选大容量版本，我帮您查下有没有货。不确定的话先拍这款试试，不够用再换也行', '容量,够用,大容量,换货' AS tags, '容量说明与换货保障' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_product_consult', '有几个颜色？能不能都看看', '亲，有黑色、白色、蓝色三个颜色，我给您拍个对比图，您看下哪个顺眼。不同颜色价格一样，您选好告诉我，我帮您确认库存', '颜色,对比图,库存,确认' AS tags, '颜色选择与对比图提供' AS source_summary, 81 AS score
  UNION ALL SELECT 'general_product_consult', '是不是全新未拆封的？别翻新机', '亲，全新未拆封的，原厂塑封没动过。我拍了封条和包装盒细节图给您看，收到货您检查封条完好就行。翻新机我们绝对不做的，验货发现问题假一赔十', '全新,未拆封,封条,翻新' AS tags, '全新未拆封确认与翻新拒绝' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_product_consult', '生产日期是什么时候？别库存机', '亲，生产日期是今年上半年的，不是库存机。我拍了机身序列号和生产日期标签给您看，新鲜出厂的。库存机序列号日期会很久，您可以对比', '生产日期,库存机,序列号,新鲜' AS tags, '生产日期说明与库存机排查' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '能不能验货？不走验货不放心', '亲，支持验货的，可以走闲鱼验货宝，也可以去专柜验货或者得物鉴定。验货费您出，验不过我全退包括邮费。正品才敢这么承诺，您放心', '验货,验货宝,专柜,得物' AS tags, '验货支持与验不过兜底' AS source_summary, 90 AS score
  UNION ALL SELECT 'general_product_consult', '重不重？搬动方便吗', '亲，这款大约X公斤，不算重，大人搬动没问题。如果您经常需要搬动，我推荐轻量版，会轻不少。您看下哪种适合，我帮您确认', '重量,搬动,轻量版,推荐' AS tags, '重量说明与轻量版推荐' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_product_consult', '有没有认证？安全标准达不达标', '亲，这款通过了XX认证和XX安全标准，有认证证书，您需要可以发您看。安全方面完全达标，您放心使用。认证不达标的产品我们不会卖的', '认证,安全,标准,证书' AS tags, '安全认证说明与证书提供' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_product_consult', '包装里都有什么？别少东西', '亲，包装内有主机、配件、说明书、保修卡、防伪卡，全套齐全。我拍了开箱视频给您看，您收到对照清单检查就行。少了任何东西我补发', '包装,清单,开箱,补发' AS tags, '包装清单说明与开箱验证' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_product_consult', '这个型号是最新款吗？别买到老款了', '亲，这款是今年的最新款，比老款升级了XX功能。我拍了型号标签给您看，您对比下官网信息。如果收到是老款，我给您退换并补偿', '型号,最新款,老款,退换' AS tags, '型号新旧确认与老款退换' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_product_consult', '能不能拍个视频看看实物？图片看不出质感', '亲，当然可以，我给您拍一段实物视频，自然光下拍的，您看下真实质感。还有什么细节想看的告诉我，我帮您补拍，您看满意再拍', '视频,实物,质感,自然光' AS tags, '实物视频展示与细节补拍' AS source_summary, 87 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 价格优惠 general_price_discount（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_price_discount' AS code, '能便宜点吗？再少点就拍' AS question, '亲，这个价格已经很实在了，您诚心要的话我给您少XX，再送您个小赠品，这波真不亏。您看行就拍，行不行我也理解' AS answer, '砍价,让利,赠品,成交' AS tags, '适度让利加赠品促成交易' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_price_discount', '还能少吗？我觉得还能再低', '亲，这已经是我的底价了，再低就亏本了。不过您要是诚心要，我给您包邮并送个配件，这比直接降价还划算。您看这样可以吗', '砍价,底价,包邮,配件' AS tags, '二次砍价应对与包邮配件替代让利' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '包邮吗？不包邮不划算', '亲，这款默认包邮的，您不用额外出运费。偏远地区可能需要补差价，我帮您查下。如果偏远地区需要补的话我会提前告诉您，不会让您多花冤枉钱', '包邮,运费,偏远,差价' AS tags, '包邮说明与偏远差价透明' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '多买有优惠吗？我买好几件', '亲，多买当然有优惠，您买3件以上我给您打XX折，5件以上再送一件同款。您报下要买几件，我帮您算个最优惠的方案', '多买,优惠,折扣,赠品' AS tags, '多买优惠方案与阶梯折扣' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_price_discount', '有学生价吗？我是学生预算有限', '亲，支持学生优惠的，您发个学生证照片给我，我给您额外减XX元。学生党不容易，能优惠的我尽量给您优惠，您看这样可以吗', '学生,优惠,学生证,减价' AS tags, '学生优惠验证与额外减价' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '我是老客户了，上次买过，有没有老客优惠', '亲，感谢您回头，老客户肯定有优惠的。我给您额外减XX元，再送您个配件。以后您介绍朋友来我也给您优惠，做长期生意的', '老客户,回头,优惠,介绍' AS tags, '老客户优惠与口碑转介绍激励' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '能再送点啥吗？光降价不够意思', '亲，行，我再送您一个XX配件，单买也要XX元的，算下来您又省了一笔。您看这波诚意够不够，够的话就拍', '赠品,配件,让利,成交' AS tags, '赠品策略促单与价值感营造' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '这价格最低了吗？别忽悠我', '亲，这确实是我的底价了，再低真亏本。您可以对比下同款的价格，我这个已经很实在了。要不您拍下，我给您包邮加赠品，等于又省了不少', '底价,对比,包邮,赠品' AS tags, '底价确认与对比引导' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '给个实惠价，诚心要别墨迹', '亲，行，诚心要就给实惠价，XX包邮再送配件，这价格我卖了好几十单了，老客户都认可的。您看行就拍，我马上给您发货', '实惠价,诚心,包邮,赠品' AS tags, '诚心报价与销量背书促单' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '别人家比你便宜XX，你能不能同价', '亲，便宜的可能成色或版本不一样，您对比下细节图就知道了。我们家保证正品行货，支持验货，品质有保障。您诚心要我给您少XX，但同价做不到，毕竟品质不一样', '价格对比,成色,正品,让利' AS tags, '价格对比应对与品质差异说明' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_price_discount', '我诚心要，给个一口价别再加了', '亲，行，一口价XX包邮，包含所有配件，不会再加价。您满意就拍，不满意我也不强求。这个价我已经是亏着邮费在做了', '一口价,诚心,包邮,成交' AS tags, '一口价报价与成交促单' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '能不能抹个零？就差那几块钱', '亲，行，抹零没问题，XX就XX，几块钱的事，交个朋友。您拍下后我改价，或者您直接按现价拍，差价我退您，都行', '抹零,改价,交朋友' AS tags, '抹零让利与改价流程' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_price_discount', '买两件能打折吗？我朋友也要一件', '亲，买两件给您打XX折，比单买省XX。您和朋友一人一件，分摊下来更划算。我帮您改价，您拍两件就行', '多件,折扣,改价,划算' AS tags, '多件折扣与改价操作' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '第一次买有优惠吗？新客有没有福利', '亲，新客有优惠的，您第一次买我给您减XX元，再送个配件。满意的话下次再来还有老客优惠，您看这样行吗', '新客,优惠,减价,配件' AS tags, '新客优惠与复购引导' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '能不能分期？一次性付有点吃力', '亲，闲鱼支持花呗分期的，您下单时选花呗支付就能分期，免息期数看平台活动。我这边价格不变，您分期还压力小点', '分期,花呗,免息,支付' AS tags, '分期支付方案与花呗引导' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_price_discount', '这个价含运费吗？别到时又加邮费', '亲，这个价是含运费的，包邮价，不会再加邮费。偏远地区也基本覆盖，如果个别偏远地区需要补差价我会提前告诉您，不会偷偷加价', '含运费,包邮,透明,偏远' AS tags, '含运费说明与透明定价' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_price_discount', '能不能再降一点？就差XX元我就拍了', '亲，这样吧，差XX元我给您抹掉，再送个XX配件，算下来比降XX还划算。您看这样可以拍了吧，再低真做不了了', '让步,抹零,赠品,成交' AS tags, '最后让步与赠品替代降价' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '我帮你宣传，便宜点行不行？带朋友来', '亲，感谢您愿意推荐，这样吧，您先按现价拍，我送您个配件，您介绍朋友来我给朋友也优惠，再返您一张优惠券。比直接降价更划算，您看行吗', '宣传,推荐,返券,配件' AS tags, '口碑营销应对与返券激励' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '预算有限，最多XX能出吗？不行就算了', '亲，XX确实低了点，但您诚心要我也不想错过。这样吧，XX我做不到，但XX我可以，再送您个配件，您看行不行，行就拍', '预算,谈判,让步,成交' AS tags, '预算谈判与适度让步促单' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '你这价格砍得太多了我不卖', '亲，理解您的想法，但这款成本确实不低，再低我真亏本。您看这样，价格不降了，我给您加个配件再包邮，等于变相优惠了，您看可以吗', '拒绝,过度砍价,配件,包邮' AS tags, '拒绝过度砍价与替代方案' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '这个价能保价吗？别我买了就降价', '亲，可以的，您买后7天内如果降价我补差价给您。不过说实话这价格已经是底价了，降的可能性很小，您放心拍', '保价,补差价,底价,承诺' AS tags, '保价承诺与底价信心' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '能不能用优惠券？我有平台券', '亲，可以的，平台优惠券您下单时直接用就行，和我的价格叠加。我这边价格已经是优惠价了，再叠加券更划算，您赶紧用别过期了', '优惠券,平台券,叠加,划算' AS tags, '优惠券叠加说明与使用引导' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_price_discount', '量大能不能给批发价？我打算拿一批', '亲，量大的话可以给批发价，您报下大概要多少，我帮您算批发价。不过批发需要确认库存够不够，我先帮您查下仓库', '批发,量大,库存,批发价' AS tags, '批发价方案与库存确认' AS source_summary, 87 AS score
  UNION ALL SELECT 'general_price_discount', '价格能不能再谈谈？我觉得还有空间', '亲，可以谈，您报个您心理价位，我看能不能做。能做我给您做，不能做我也如实说，不浪费您时间。咱们诚心谈，总能找到双方都满意的点', '议价,心理价位,诚心,协商' AS tags, '议价空间引导与诚心协商' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_price_discount', '急出最低多少？我全款秒', '亲，全款秒的话我给您最低价XX，这比挂价低了XX，够诚意了吧。您现在拍我马上改价，今天就给您发货', '急售,全款,最低价,秒拍' AS tags, '急售应对与全款优惠促单' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_price_discount', '加价能不能发顺丰？我急用', '亲，可以的，补XX差价我帮您发顺丰，时效快很多。您下单后备注改顺丰，差价补给我就行，我帮您改快递', '加价,顺丰,差价,改快递' AS tags, '加价改顺丰方案与差价说明' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_price_discount', '这个价是终价吗？别拍完又加价', '亲，是的，一口价XX包邮，包含所有费用，不会再加价。您放心拍，拍下就是这个价，我绝不加价。有任何问题我兜底', '终价,一口价,包邮,承诺' AS tags, '终价确认与不加价承诺' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_price_discount', '能不能先付定金？我还没凑够钱', '亲，闲鱼不支持定金模式，需要全款拍下。不过您可以用花呗分期，先拿到货再慢慢还，压力小很多。您看要不要试试分期', '定金,全款,花呗,分期' AS tags, '定金模式说明与分期替代方案' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_price_discount', '朋友介绍的，能优惠吗？', '亲，朋友介绍的当然有优惠，我给您减XX元，再送个配件。您朋友也是老客户了，介绍来的我都给优惠，您满意的话也帮我推荐推荐', '介绍,优惠,减价,推荐' AS tags, '朋友介绍优惠与口碑激励' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_price_discount', '你这价格对标的是哪家？怎么这么贵', '亲，这个价格对标的是专柜价，已经是专柜的XX折了。我们家保证正品行货，支持验货，和那些来路不明的低价货不一样。您对比品质就知道值不值了', '价格,对标,专柜,正品' AS tags, '价值对标说明与品质背书' AS source_summary, 87 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;

-- ============ 账号登录 general_account_login（30条） ============
INSERT IGNORE INTO ai_cs_learned_kb (
    category_id, question, answer, tags, source_summary,
    content_hash, score, review_status, enabled, vector_indexed,
    source_count, source_conv_ids, learn_batch_id, sensitive_filtered,
    source_type, deleted, created_time, updated_time
)
SELECT c.id, q.question, q.answer, q.tags, q.source_summary,
       MD5(CONCAT(q.question, q.answer)), q.score, 'approved', 1, 1,
       1, NULL, 'seed-v1.50', 1, 'seed', 0, NOW(), NOW()
FROM (
  SELECT 'general_account_login' AS code, 'cookie失效了怎么办？突然登不上了' AS question, '亲，cookie失效是正常的，闲鱼cookie一般几天到两周过期。需要重新获取cookie重新登录，我发您获取教程，跟着操作就行，很简单几步搞定' AS answer, 'cookie,失效,登录,教程' AS tags, 'cookie失效处理与重新获取指导' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_account_login', '登不上了，一直转圈进不去', '亲，可能是网络问题或者APP缓存过多。您试试切换网络、清下APP缓存、重启APP再登录。如果还是不行，卸载重装闲鱼试试。还不行的话我帮您排查', '登录,转圈,网络,缓存,重装' AS tags, '登录失败排查步骤指引' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_account_login', '扫码登录没反应，扫了半天没动静', '亲，可能是二维码过期了或者网络延迟。您刷新下二维码重新扫试试，扫码时确保网络畅通。如果还是没反应，试试切换网络或者重启闲鱼APP再扫', '扫码,无反应,二维码,网络' AS tags, '扫码无反应排查与重试引导' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_account_login', '二维码过期了怎么刷新？', '亲，二维码一般几十秒到几分钟就过期了，过期后点一下二维码区域或者刷新页面就会生成新的。您重新扫新的二维码就行，扫的时候动作快点', '二维码,过期,刷新,重新扫' AS tags, '二维码过期刷新操作指引' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '换手机登录要重新扫码吗？', '亲，需要的，新手机上打开闲鱼登录页，选择扫码登录，用旧手机扫一下就行。如果旧手机不在身边，可以用账号密码或验证码登录', '换手机,扫码,登录,验证码' AS tags, '换设备登录方式说明' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_account_login', '账号被冻结了怎么办？什么原因', '亲，账号被冻结可能是违规操作、频繁登录异常或被举报。您去闲鱼安全中心查看冻结原因，按提示申诉就行。一般提交申诉后1到3个工作日审核，我帮您看看怎么操作', '冻结,违规,申诉,安全中心' AS tags, '账号冻结原因排查与申诉引导' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_account_login', '怎么解绑？我想换个账号', '亲，您在闲鱼设置里找到账号管理，选择解绑就行。解绑后可以重新绑定新账号。如果解绑遇到问题，可能是安全验证没通过，按提示完成验证再解绑', '解绑,换账号,设置,验证' AS tags, '解绑操作步骤指引' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '能改密码吗？我觉得密码不安全了', '亲，可以的，在闲鱼设置里找到安全设置，选择修改密码，输入旧密码和新密码就行。建议密码包含字母数字组合，别用太简单的。改完其他设备会自动退出', '改密码,安全设置,密码组合' AS tags, '修改密码操作与安全建议' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_account_login', '在这登录安全吗？会不会被盗', '亲，很安全的，登录信息是加密传输的，不会泄露。建议您不要在公共设备上登录，定期改密码，开启双重验证，这样账号更安全。有异常登录会收到提醒的', '安全,登录,加密,双重验证' AS tags, '登录安全说明与防护建议' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_account_login', '信息会泄露吗？我不放心', '亲，您放心，我们的系统是加密传输的，登录信息不会明文存储，也不会提供给第三方。建议您开启账号安全验证，定期检查登录记录，有异常及时改密码', '泄露,加密,安全验证,登录记录' AS tags, '隐私保护说明与安全建议' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_account_login', '验证码收不到，登录不了', '亲，验证码收不到可能是信号不好或者被拦截了。您检查下短信拦截记录，或者等几分钟重发。也可以试试语音验证码或者切换登录方式。实在不行我帮您排查', '验证码,收不到,短信,语音' AS tags, '验证码收不到排查与替代方案' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_account_login', '登录提示环境异常怎么回事？', '亲，可能是您换了设备或者网络环境变化导致的。系统检测到和平时登录环境不一致就会提示。您按提示完成安全验证就行，验证通过就能正常登录了', '环境异常,设备,验证,安全' AS tags, '登录环境异常解释与验证引导' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_account_login', '账号被盗了！怎么办急', '亲，您别急，立刻去闲鱼安全中心冻结账号，然后修改密码，再联系闲鱼客服申诉。越快处理损失越小。您把登录记录截图保存，方便申诉时用。我帮您一步步操作', '被盗,冻结,改密码,申诉,紧急' AS tags, '盗号紧急处理流程与申诉指引' AS source_summary, 92 AS score
  UNION ALL SELECT 'general_account_login', '怎么注销账号？不想用了', '亲，在闲鱼设置里找到账号管理，选择注销账号。注销前确保没有未完成的订单和退款。注销后账号无法恢复，数据会清除，您确认好再操作。有问题我帮您查', '注销,账号,订单,数据' AS tags, '注销流程与注意事项说明' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '能同时登录吗？手机和电脑都登', '亲，可以的，闲鱼支持多设备同时登录，手机和电脑可以同时在线。不过建议不要在太多设备登录，安全起见定期检查登录设备，不用的设备及时退出', '多设备,同时登录,安全,退出' AS tags, '多设备登录说明与安全建议' AS source_summary, 81 AS score
  UNION ALL SELECT 'general_account_login', '登录提示设备未信任怎么办？', '亲，新设备首次登录需要安全验证，您按提示完成验证就行，验证通过设备就信任了。如果验证收不到验证码，可以换其他验证方式试试', '设备,信任,验证,新设备' AS tags, '新设备信任验证操作指引' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_account_login', '实名认证怎么弄？显示要认证', '亲，在闲鱼设置里找到实名认证，输入姓名和身份证号，再做人脸验证就行。认证后账号功能更全，交易也更安全。几分钟就能搞定，我发您步骤', '实名认证,身份证,人脸,安全' AS tags, '实名认证操作步骤指引' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_account_login', '账号被封了怎么申诉？能解封吗', '亲，可以的，去闲鱼安全中心提交申诉，写明情况和申诉理由，附上相关证据。一般1到3个工作日审核。如果是误封，解封很快。我帮您看怎么写申诉理由比较好', '封号,申诉,解封,安全中心' AS tags, '封号申诉流程与理由撰写指导' AS source_summary, 88 AS score
  UNION ALL SELECT 'general_account_login', 'cookie怎么获取？我不会弄', '亲，很简单，我发您图文教程。电脑浏览器打开闲鱼官网登录，按F12打开开发者工具，在Application里找到cookie复制就行。跟着教程一步步来，几分钟搞定', 'cookie,获取,教程,开发者工具' AS tags, 'cookie获取教程与操作指引' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_account_login', '登录后数据不同步怎么办？显示不一样', '亲，可能是网络延迟导致数据没同步。您试试下拉刷新或者退出重新登录。如果还是不同步，清下APP缓存再试。还不行的话可能是服务器延迟，等一会就好', '数据,同步,刷新,缓存' AS tags, '数据不同步排查与处理' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '扫码登录安全吗？会不会被截取', '亲，很安全的，扫码登录是加密传输的，二维码有时效且一次性，不会被截取。比密码登录更安全，因为不输入密码。建议您优先用扫码登录', '扫码,安全,加密,一次性' AS tags, '扫码登录安全性说明与推荐' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_account_login', '账号能转让吗？我想给别人', '亲，闲鱼账号不支持转让的，账号是实名认证的，和身份信息绑定。建议您注销重新注册，或者让对方用自己的账号。转让有安全风险，不建议操作', '转让,实名,注销,风险' AS tags, '账号转让限制说明与风险提醒' AS source_summary, 80 AS score
  UNION ALL SELECT 'general_account_login', '忘记密码了怎么办？登不进去', '亲，在登录页点忘记密码，输入绑定的手机号获取验证码，验证后设置新密码就行。如果手机号也换了，走账号申诉流程，我帮您看怎么操作', '忘记密码,验证码,申诉,手机号' AS tags, '找回密码流程与申诉兜底' AS source_summary, 85 AS score
  UNION ALL SELECT 'general_account_login', '登录次数太多被限制了怎么办', '亲，频繁登录会被系统限制，一般等30分钟到1小时就会自动解除。您先别反复尝试，等限制解除后再登录。如果紧急需要登录，可以试试换网络或者设备', '限制,频繁登录,等待,换网络' AS tags, '登录限制处理与等待建议' AS source_summary, 81 AS score
  UNION ALL SELECT 'general_account_login', '怎么换绑手机号？我手机号不用 了', '亲，在闲鱼设置里找到账号安全，选择更换手机号，输入新手机号验证码就行。如果旧手机号已经收不到验证码，走账号申诉流程，提供身份信息验证后换绑', '换绑,手机号,验证,申诉' AS tags, '换绑手机号流程与申诉兜底' AS source_summary, 83 AS score
  UNION ALL SELECT 'general_account_login', '账号异常被限制登录了怎么解封', '亲，被限制登录可能是违规或安全风险。您去闲鱼安全中心查看限制原因，按提示申诉解封。一般提交申诉后1到3个工作日审核。我帮您看怎么申诉比较好', '限制登录,解封,申诉,安全中心' AS tags, '限制登录解封流程与申诉指导' AS source_summary, 86 AS score
  UNION ALL SELECT 'general_account_login', 'cookie多久会失效？要不要经常换', '亲，cookie一般7到14天会过期，看闲鱼的安全策略。建议您一周左右更新一次cookie，避免突然失效影响使用。我帮您设置提醒，到期前通知您更新', 'cookie,失效,周期,提醒' AS tags, 'cookie失效周期与更新提醒' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '多个账号怎么管理？切换方便吗', '亲，闲鱼支持多账号切换，在设置里添加账号就行，切换不需要重新登录。不过建议同一设备不要登太多账号，容易被风控。2到3个账号比较安全', '多账号,管理,切换,风控' AS tags, '多账号管理与风控建议' AS source_summary, 84 AS score
  UNION ALL SELECT 'general_account_login', '登录后闪退怎么回事？一直进不去', '亲，可能是APP版本问题或者缓存冲突。您试试清下APP缓存、更新到最新版本、重启手机再试。如果还是闪退，卸载重装闲鱼试试。还不行我帮您排查', '闪退,缓存,版本,重装' AS tags, '登录闪退排查与处理步骤' AS source_summary, 82 AS score
  UNION ALL SELECT 'general_account_login', '账号安全怎么保障？我怕被盗', '亲，建议您做到几点：开启双重验证、定期改密码、不点击不明链接、不在公共设备登录、定期检查登录设备。做到这些基本不会被盗。有异常登录系统会提醒您', '安全,双重验证,密码,防护' AS tags, '账号安全保障建议与防护措施' AS source_summary, 85 AS score
) q
JOIN ai_cs_kb_category c ON c.code = q.code AND c.deleted = 0 AND c.parent_id IS NOT NULL;
