from pathlib import Path
from qtpy.QtGui import QGuiApplication
from qtpy.QtCore import Qt
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)
mode = 'light'
try:
    if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark:
        mode = 'dark'
except Exception as e:
    logger.error(f'failed to detect dark mode: {e}')
logger.info(f'using {mode} mode')
css = Path(__file__).parent / f"stylesheet-{mode}.css"
DEFAULT_STYLESHEET = css.read_text()
