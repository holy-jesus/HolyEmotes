from .any import Any
from .avif import AVIF
from .gif import GIF
from .webp import WEBP

FORMATS = {"image/avif": AVIF, "image/gif": GIF, "image/webp": WEBP}
