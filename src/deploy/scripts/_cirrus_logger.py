"""
This file mainly acts as a filler, with a default logger that doesn't do anything.

The intention is that anyone using the runcirrus script can overwrite the
_cirrus_logger.py and add their own loghandler. The logger will be imported in
runcirrus.py and used there.

The implementation is a bit rough, could be solved without overwriting files...
"""

from logging import getLogger

logger = getLogger(__name__)
