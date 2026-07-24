
from .routes import ai_transaction_engine, opportunity, workflow
from fastapi import APIRouter
from .routes import account, order, dashboard, items, auto_delivery, auto_reply, kami, messages, system, internal
from .routes import quick_reply as quick_reply_module
from .routes import sse as sse_module
from .routes import misc as misc_module
from .routes import restful as restful_module
from .routes import auto_category as auto_category_module
from .routes import knowledge_base as knowledge_base_module
from .routes import auto_reply_scope as auto_reply_scope_module
from .routes import captcha as captcha_module
from .routes import feishu as feishu_module
from .routes import mall_category as mall_category_module
from .routes import slider_api as slider_api_module

api_router = APIRouter()
api_router.include_router(ai_transaction_engine.router, tags=['aiTransaction'])
api_router.include_router(opportunity.router, tags=['opportunity'])
api_router.include_router(workflow.router, tags=['workflow'])
api_router.include_router(account.router, tags=["account"])
api_router.include_router(order.router, tags=["order"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(items.router, tags=["items"])
api_router.include_router(auto_delivery.router, tags=["autoDelivery"])
api_router.include_router(auto_reply.router, tags=["autoReply"])
api_router.include_router(quick_reply_module.router, tags=["quickReply"])
api_router.include_router(kami.router, tags=["kami"])
api_router.include_router(messages.router, tags=["messages"])
api_router.include_router(system.router, tags=["sysSetting"])
api_router.include_router(system.ai_provider_router, tags=["aiProvider"])
api_router.include_router(system.login_device_router, tags=["loginDevice"])
api_router.include_router(system.operation_log_router, tags=["operationLog"])
api_router.include_router(system.notification_router, tags=["notification"])
api_router.include_router(system.system_info_router, tags=["system"])
api_router.include_router(internal.router, tags=["internal"])
# Added routes for frontend compatibility
api_router.include_router(sse_module.router, tags=["sse"])
api_router.include_router(misc_module.media_router, tags=["media"])
api_router.include_router(misc_module.image_router, tags=["image"])
api_router.include_router(misc_module.captcha_router, tags=["captcha"])
api_router.include_router(captcha_module.router, tags=["captchaV2"])
api_router.include_router(misc_module.backup_router, tags=["backup"])
api_router.include_router(misc_module.excel_router, tags=["excel"])
api_router.include_router(misc_module.goods_sku_router, tags=["goodsSku"])
api_router.include_router(misc_module.business_router, tags=["businessOpportunity"])
api_router.include_router(misc_module.data_panel_router, tags=["dataPanel"])
api_router.include_router(misc_module.navigation_router, tags=["navigation"])
api_router.include_router(misc_module.qrlogin_router, tags=["qrlogin"])
api_router.include_router(misc_module.websocket_router, tags=["websocket"])
api_router.include_router(misc_module.notification_router, tags=["notificationExt"])
api_router.include_router(misc_module.operation_log_router, tags=["operationLogExt"])
api_router.include_router(restful_module.router, tags=["restful"])
api_router.include_router(auto_category_module.router, tags=["autoCategory"])
api_router.include_router(auto_category_module.categories_router, tags=["categories"])
api_router.include_router(knowledge_base_module.router, tags=["knowledgeBase"])
api_router.include_router(auto_reply_scope_module.router, tags=["autoReplyScope"])
api_router.include_router(feishu_module.router, tags=["feishu"])
api_router.include_router(mall_category_module.router, tags=["mallCategory"])
api_router.include_router(slider_api_module.router, tags=["slider-api"])
