import shutil
import os

from Core.Config import Config as CoreConfig, _P
from Services.Utils.OSUtils import OSUtils


def _resolveFfmpegPath() -> str:
    bundled = _P(CoreConfig.DEPENDENCIES_ROOT, f"ffmpeg{OSUtils.getExecutableType()}")
    if os.path.isfile(bundled):
        return bundled
    system = shutil.which("ffmpeg")
    if system:
        return system
    return bundled


class Config:
    PATH = _resolveFfmpegPath()

    KILL_TIMEOUT = 10000
