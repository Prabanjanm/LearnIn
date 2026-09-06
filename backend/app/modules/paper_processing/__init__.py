"""
Question Paper Processing pipeline.

This package attaches its own console handler at INFO level, scoped only to
`app.modules.paper_processing.*` loggers - the rest of the app is untouched.
Every submodule here uses `logging.getLogger(__name__)` as usual; because
those names all live under this package, their records propagate up to this
handler automatically. The goal is one thing: when a processing job is
stuck or fails, `background.py`'s stage-by-stage logs (download, validate,
watermark, analyze, extract, detect questions, detect visuals, save) show up
in the server console without needing the whole app's log level turned up.
"""
import logging

_logger = logging.getLogger(__name__)

if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[paper-processing] %(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    # Don't also hand these records to the root logger's handlers (if any) -
    # this package's own handler above is already printing them, and this
    # avoids a duplicated line per message.
    _logger.propagate = False
