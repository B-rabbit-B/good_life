"""全部 SDK 能力。新增模块的能力在这里追加。"""

from app.sdk.capabilities import cycle, fitness, medical, nutrition, profile

ALL = [
    *profile.CAPABILITIES,
    *cycle.CAPABILITIES,
    *medical.CAPABILITIES,
    *nutrition.CAPABILITIES,
    *fitness.CAPABILITIES,
]
