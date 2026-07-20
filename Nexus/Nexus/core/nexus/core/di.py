"""Simple thread-safe dependency injection container."""
from __future__ import annotations

import threading
from typing import Callable, TypeVar, cast

from nexus.core.exceptions import ProviderNotRegisteredError

T = TypeVar("T")


class Container:
    def __init__(self) -> None:
        self._instances: dict[type, object] = {}
        self._factories: dict[type, Callable[[], object]] = {}
        self._singleton_flags: dict[type, bool] = {}
        self._lock = threading.RLock()

    def register_instance(self, interface: type[T], instance: T) -> None:
        with self._lock:
            self._instances[interface] = instance

    def register_factory(self, interface: type[T], factory: Callable[[], T], *, singleton: bool = True) -> None:
        with self._lock:
            self._factories[interface] = factory
            self._singleton_flags[interface] = singleton

    def resolve(self, interface: type[T]) -> T:
        with self._lock:
            if interface in self._instances:
                return cast(T, self._instances[interface])

            if interface in self._factories:
                factory = self._factories[interface]
                if self._singleton_flags.get(interface, True):
                    instance = factory()
                    self._instances[interface] = instance
                    return cast(T, instance)
                else:
                    return cast(T, factory())

            raise ProviderNotRegisteredError(f"No provider registered for interface {interface.__name__}")

    def is_registered(self, interface: type) -> bool:
        with self._lock:
            return interface in self._instances or interface in self._factories

    def clear(self) -> None:
        with self._lock:
            self._instances.clear()
            self._factories.clear()
            self._singleton_flags.clear()