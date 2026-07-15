"""测试闲鱼搜索接口调用"""
import hashlib
import json
import time
import requests

APP_KEY = "34839810"
H5_API_BASE = "https://h5api.m.goofish.com/h5"
SEARCH_MTOP_API = "mtop.taobao.idlemtopsearch.pc.search"

# 从数据库获取的cookie
cookie_str = (
    "t=99a0a0827fcdc44b322f9d2b966d123f; cna=KyZ8H7DmRGMCAQAAAABbo0kM; "
    "isg=BNTUgippQqPo0tUNCZn9hxZGpRJGLfgXEc6y0261-9_iWXejlj27pz7QXVFBoTBv; "
    "tracknick=tb710546863; "
    "havana_lgc2_77=eyJoaWQiOjIyMTE0MjI0NjQzNDEsInNnIjoiYzc3Y2ZjNmUzMzA4NGVhYTQyZjYwNjhiODhmYjAwNjciLCJzaXRlIjo3NywidG9rZW4iOiIxTzlCRGxsQk1QYnZ0ZkFleG5WVUZOZyJ9; "
    "_hvn_lgc_=77; havana_lgc_exp=1783362690512; unb=2211422464341; "
    "xlly_s=1; cookie2=1598ff80e69aca04933bbd93ef4f7a9c; mtop_partitioned_detect=1; "
    "_m_h5_tk=fbd6bb67cc4a2aad0a1cd125d680c958_1782475703083; "
    "_m_h5_tk_enc=3a945cc9091e66b74bf7a89670612b45; _samesite_flag_=true; "
    "sgcookie=E100H9cLr8%2B6ljW6mNzn6iq2KV9W8dX1rkD13Vegyuiy%2BJv%2F2AkQnPyiWHK2C%2FvfauUHToSq%2BfeX5MRxugXlV4cMb%2Fr9RlXLj3Hd%2FVUM%2BTLdMiCYEb43mNgWoNW2%2FA8aGAUC; "
    "csg=4617e833; _tb_token_=3785e136e3fd6; sdkSilent=1782553825339; "
    "tfstk=gFt-d_fs_jcllUnj6u0Dt_8lKGkDwqvyrQJ_x6fuRIdvCdPlR3jk9ydkLBbIagxpMpOtU9cyx882sdZkq4S3vgSFAfcijcDyUMSQ0HBDF_JX39McFo8n4vjFAfcLok_rXMRoRMWdPKMAK95COB_7ht1VIusCNwNblO1fOMOCRS_fK94QO9_QhxBFG6sCABsjH9ffOMsBOKGagufYatZponACa7aPZkZBDTQjoL1bRs-AeaC6F3EQAJWRy195GfYeBwbXLwKULkQDFFRFCQNSwM9ABCB9w22FwE9Mq_vTQk9A2HpBRZHSVKIRww-frchf2eOyva88LAJfVI8N_agqgtKkjwCNkSGWnKC5Wedogk1kWKOASnV0ji96kiIyihxttIFG694SHxUU8a6VSYnF4W9VAoXAsYdu8y7IGtCiHxUU8a6VH1DR-yzFRj1.."
)

token = "fbd6bb67cc4a2aad0a1cd125d680c958"

t_ms = int(time.time() * 1000)

# 使用与接口文档完全相同的 data 格式和字段顺序
data_obj = {
    "pageNumber": 1,
    "keyword": "ddr4",
    "fromFilter": False,
    "rowsPerPage": 30,
    "sortValue": "",
    "sortField": "",
    "customDistance": "",
    "gps": "",
    "propValueStr": {},
    "customGps": "",
    "searchReqFromPage": "pcSearch",
    "extraFilterValue": "{}",
    "userPositionJson": "{}",
}
data = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))

sign = hashlib.md5(f"{token}&{t_ms}&{APP_KEY}&{data}".encode()).hexdigest()

url = f"{H5_API_BASE}/{SEARCH_MTOP_API}/1.0/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.goofish.com/",
    "Origin": "https://www.goofish.com",
    "Content-Type": "application/x-www-form-urlencoded",
}

form_data = {
    "jsv": "2.7.2",
    "appKey": APP_KEY,
    "t": str(t_ms),
    "sign": sign,
    "v": "1.0",
    "type": "originaljson",
    "accountSite": "xianyu",
    "dataType": "json",
    "timeout": "20000",
    "api": SEARCH_MTOP_API,
    "sessionOption": "AutoLoginOnly",
    "spm_cnt": "a21ybx.search.0.0",
    "spm_pre": "a21ybx.search.searchActivate.8.55877bcfXF6kjV",
    "log_id": "55877bcfXF6kjV",
    "data": data,
}

session = requests.Session()
for part in cookie_str.split(";"):
    part = part.strip()
    if "=" in part:
        key, _, value = part.partition("=")
        session.cookies.set(key.strip(), value.strip(), domain=".goofish.com")

print(f"URL: {url}")
print(f"token: {token}")
print(f"t: {t_ms}")
print(f"sign: {sign}")
print(f"data: {data}")
print("---Sending request...---")

resp = session.post(url, headers=headers, data=form_data, timeout=30)
result = resp.json()
ret = result.get("ret", [])
print(f"ret: {ret}")

if result.get("data"):
    rdata = result["data"]
    if isinstance(rdata, dict):
        print(f"data keys: {list(rdata.keys())[:10]}")
        result_info = rdata.get("resultInfo", {})
        if result_info:
            print(f"resultInfo: {json.dumps(result_info, ensure_ascii=False)[:200]}")
        result_list = rdata.get("resultList", [])
        print(f"resultList count: {len(result_list)}")
        if result_list:
            first = result_list[0]
            print(f"first item keys: {list(first.keys())[:10]}")
    else:
        print(f"data type: {type(rdata)}")
else:
    print(f"data: None")
    print(f"full response: {json.dumps(result, ensure_ascii=False)[:500]}")
