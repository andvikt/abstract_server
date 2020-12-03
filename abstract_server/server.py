import abc
import asyncio
import logging
from contextlib import AbstractAsyncContextManager

DEFAULT_START_TIMEOUT = 60


class NotStarted(Exception):
    pass


class AbstractServer(AbstractAsyncContextManager, abc.ABC):
    """
    Класс для реализации базовой функциональности любого асинхронного сервера.
    Гарантирует наличие методов start и stop + то же самое в исполнении контекст-менеджера
    """
    start_timeout = DEFAULT_START_TIMEOUT

    @abc.abstractmethod
    async def run(self):
        """
        Основной код, который исполняется после старта.
        Внимание! Внутри необходимо вызвать self.started.set()
        Если этого не произойдет в течение дефолтного времени ожидания, вся программа будет завершена с критической
        ошибкой

        :return:
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def clean(self):
        """
        Метод вызывается во время завершения работы
        :return:
        """
        raise NotImplementedError

    @property
    def lg(self):
        lg = logging.getLogger(self.__class__.__name__)
        return lg

    def __init__(self):
        self.task: asyncio.Task = None
        self.started = asyncio.Event()

    def start(self):
        if self.task is not None:
            raise ValueError(f'{self} already started')
        self.task = asyncio.create_task(self._start())

    def stop(self):
        if self.task is None:
            return
        else:
            self.task.cancel()
        return self.wait_stopped()

    async def wait_stopped(self):
        await self.task
        await self.clean()
        self.task = None
        self.started.clear()

    async def _start(self):
        asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self.started.wait(), self.start_timeout)
        except asyncio.TimeoutError:
            self.lg.critical(f'not started after {self.start_timeout}')
            raise NotStarted(f'{self} not started after {self.start_timeout} seconds')

    async def _run(self):
        try:
            await self.run()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            self.lg.critical(f'{self} stopped running with error: {exc}')
            self.lg.exception(f'while running {self}')
            raise

    async def __aenter__(self):
        self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

