"""Settings the research code and the web app share, read from the environment."""
import os

DEFAULT_CITY = os.environ.get("TRAFFICTWIN_DEFAULT_CITY", "Dhaka")           # used only for a person with no profile yet
DEFAULT_TZ = os.environ.get("TRAFFICTWIN_DEFAULT_TZ", "Asia/Dhaka")
