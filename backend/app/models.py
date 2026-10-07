"""汇总导入全部 ORM 模型，让 Base.metadata 完整。Alembic 和测试都依赖这里。"""

from app.auth import models as auth_models  # noqa: F401
from app.cycle import models as cycle_models  # noqa: F401
from app.disclaimer import models as disclaimer_models  # noqa: F401
from app.fitness import models as fitness_models  # noqa: F401
from app.medical import models as medical_models  # noqa: F401
from app.nutrition import models as nutrition_models  # noqa: F401
from app.profile import models as profile_models  # noqa: F401
