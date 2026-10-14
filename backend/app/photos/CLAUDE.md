# photos 包说明书

## 职责
- 拍照识别：处理图片 → “看图识别”用途的模型认出菜名、份量说法、估计克数与把握程度 → 匹配营养库并换算克数 → 保存草稿 → 用户修正 → 确认后才写入饮食记录，并由营养引擎评价这一餐。
- 模型只负责“看”：recognition.py 只读取约定的字段，其余全部忽略；热量与营养由 matching.py 按营养库每 100 克数值乘克数算出，与记一餐时保存的数字同一套计算与取整。
- images.py 按文件头判断格式、转正方向、去掉全部元数据（含位置）、缩小并重新编码为 JPEG；发给模型与可能保存的只能是这里的输出。原图默认不保留，用户上传时选择保留才存（加密、延迟加载）。
- 匹配不上、把握低、克数越界或用估计克数的项标为待确认（REVIEW_CONFIDENCE 等阈值，前端 contract.ts 有副本）。

## 边界
- 依赖：auth、common、db、errors、llm（看图模型）、nutrition（营养库、饮食记录、评价）、security。
- 被引用：common/body_limit.py 只取 MAX_UPLOAD_BYTES。sdk 没有拍照能力，智能体不调用本包。
- 门槛：路由用 nutrition 的 require_nutrition_user（tests/test_route_guards.py 检查）。
- 识别时不持有调用方的数据库会话：读模型配置与保存草稿各用一个短会话，调用模型期间不占事务。

## 入口
- 路由：/api/photos/recognitions 的上传、列表、详情、items 修正、confirm、discard、删除与 image（router.py）。
- 评测脚本：uv run python -m app.photos.eval_check，由用户本人用自选照片与真实看图模型运行；照片目录与结果文件不提交。
- 测试：tests/test_photo_flow.py、test_photo_images.py、test_photo_recognition.py、test_photo_eval_check.py、test_photo_docs.py。

## 禁区
- 不从模型输出取热量、营养或结论；不保存模型的说明文字。
- 未经用户确认不写饮食记录；删除识别记录不影响已经写入的饮食记录。
- 不把未经 images.py 处理的原始字节发给模型或落库（会带出 EXIF 位置）。
- 结果与日志只写菜名与克数，不写图片；测试只用内存里生成的图片与模拟模型。
