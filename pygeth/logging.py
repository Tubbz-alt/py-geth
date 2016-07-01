from __future__ import absolute_import

import os
import datetime
import logging
from io import BytesIO

import gevent
from gevent.queue import (
    Queue,
)

from .utils.filesystem import ensure_path_exists


def construct_logger_file_path(prefix, suffix):
    ensure_path_exists('./logs')
    timestamp = datetime.datetime.now().strftime(
        '{prefix}-%Y%m%d-%H%M%S-{suffix}.log'.format(
            prefix=prefix, suffix=suffix,
        ),
    )
    return os.path.join('logs', timestamp)


def get_file_logger(name, filename):
    # create logger with 'spam_application'
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(filename)
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def stream_to_queues(stream, *queues):
    for line in iter(stream.readline, b''):
        for queue in queues:
            queue.put(line)
            gevent.sleep(0.1)


def queue_to_logger(queue, *logger_functions):
    while True:
        line = queue.get()
        for fn in logger_functions:
            fn(line)
            gevent.sleep(0.1)


def queue_to_stream(queue, *streams):
    while True:
        line = queue.get()
        for stream in streams:
            stream.writeline(line)


class LoggingMixin(object):
    """
    Mixin class for GethProcess instances that logs stdout and stderr from the
    geth process to a logger.  By defuault the logger
    """
    def __init__(self, *args, **kwargs):
        super(LoggingMixin, self).__init__(*args, **kwargs)

        self._stdout_logger_queue = Queue()
        self._stdout_stream_queue = Queue()
        self.stdout_logger = get_file_logger(
            'stdout',
            construct_logger_file_path('geth', 'stdout'),
        )
        self.stdout = BytesIO()

        self._stderr_logger_queue = Queue()
        self._stderr_stream_queue = Queue()
        self.stderr_logger = get_file_logger(
            'stderr',
            construct_logger_file_path('geth', 'stderr'),
        )
        self.stdout = BytesIO()

    def start(self):
        super(LoggingMixin, self).start()

        gevent.spawn(
            stream_to_queues,
            self._proc.stdout,
            self._stdout_logger_queue,
            self._stdout_stream_queue,
        )
        gevent.spawn(
            queue_to_logger,
            self._stdout_logger_queue,
            self.stdout_logger.info,
        )
        gevent.spawn(queue_to_stream, self._stdout_stream_queue, self.stdout)

        gevent.spawn(
            stream_to_queues,
            self._proc.stderr,
            self._stderr_logger_queue,
            self._stderr_stream_queue,
        )
        gevent.spawn(
            queue_to_logger,
            self._stderr_logger_queue,
            self.stderr_logger.info,
        )
        gevent.spawn(queue_to_stream, self._stderr_stream_queue, self.stderr)