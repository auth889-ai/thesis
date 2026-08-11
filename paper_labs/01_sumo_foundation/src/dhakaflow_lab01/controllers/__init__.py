from .fixed_time import FixedTimeController
from .actuated import QueueActuatedController
from .max_pressure import MaxPressureController

CONTROLLERS = {
    "fixed_time": FixedTimeController,
    "actuated": QueueActuatedController,
    "max_pressure": MaxPressureController,
}
