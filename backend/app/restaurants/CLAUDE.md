# restaurants 包说明书

## 职责
- 附近餐厅推荐：频率限制 → 一句话需求归到固定需求词（规则优先，规则没命中时可请对话模型从词表里挑）→ 确定检索中心（GPS 坐标换算成 GCJ-02，或地址解析）→ 高德周边检索 → 按类型用营养引擎评价代表菜 → 过滤与排序 → 组装结果与导航链接。
- 过滤与排序只由规则决定（ranking.py）：被判为建议避开的类型不进推荐列表，单独返回类型与原因。
- 餐厅设置每用户一行：定位授权状态，以及用户选择记住时的粗略区域（加密，坐标取整到小数点后两位）。

## 边界
- 依赖：auth、common、config（高德密钥是服务端配置，不是用户配置）、db、disclaimer、errors、llm（需求挑词，可选）、medical、nutrition、profile、security。
- 被引用：sdk 的 nutrition.nearby_restaurants 能力（给智能体的店不含地址、坐标、导航链接与应避开的菜名）；agent 只用 amap_configured 决定是否提供这个工具。
- 门槛：路由用 nutrition 的 require_nutrition_user；没有配置高德密钥时功能关闭。
- 高德与模型的网络调用期间不持有数据库事务。

## 入口
- 路由：/api/restaurants 下的 settings、settings/consent、settings/area、needs、search（router.py）。
- 数据：data/ 下的需求词表与餐厅类型表（代表菜都是营养库里的食物编号）。
- 实测脚本：uv run python -m app.restaurants.live_check，由用户本人在服务端配置真实高德密钥后运行。
- 测试：tests/test_restaurant_flow.py、test_restaurant_rules.py、test_restaurant_amap.py、test_restaurant_agent.py、test_restaurant_live_check.py、test_restaurant_docs.py。

## 禁区
- 精确坐标、手动输入的地点原文与检索内容不入库、不写日志；逆地理只取到区县名称。
- 高德密钥只放在请求参数里，任何错误说明、异常与 repr 都不带密钥或高德返回的原文。
- 模型挑出的需求只认词表里的键，其余丢弃；排序与“避开”结论不交给模型。
- 建议只是按餐厅类别的一般性建议，不能写成该店真实菜单；测试只用模拟高德，绝不访问真实网络。
