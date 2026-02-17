"""
Tools allow agents to accomplish specialized tasks.
"""

import logging
logger = logging.getLogger("tinytroupe")

###########################################################################
# Exposed API
###########################################################################
from tinytroupe.tools.tiny_tool import TinyTool
from tinytroupe.tools.tiny_word_processor import TinyWordProcessor
from tinytroupe.tools.tiny_calendar import TinyCalendar
from tinytroupe.tools.browser_controller import BrowserController

__all__ = ["TinyTool", "TinyWordProcessor", "TinyCalendar", "BrowserController"]