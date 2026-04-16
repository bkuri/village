from __future__ import annotations

import pytest

from village.chat.transports import AsyncTransport, TransportCapabilities


def test_cannot_instantiate_abstract_transport_directly() -> None:
    with pytest.raises(TypeError):
        AsyncTransport()  # type: ignore[abstract]


def test_subclass_missing_abstract_methods_raises() -> None:
    class IncompleteTransport(AsyncTransport):
        async def start(self) -> None: ...

    with pytest.raises(TypeError):
        IncompleteTransport()  # type: ignore[abstract]


def test_subclass_must_implement_all_abstract_methods() -> None:
    class MinimalTransport(AsyncTransport):
        @property
        def name(self) -> str:
            return "minimal"

        @property
        def capabilities(self) -> TransportCapabilities:
            return TransportCapabilities()

        async def start(self) -> None: ...

        async def stop(self) -> None: ...

        async def send(self, message: str) -> None: ...

        async def receive(self) -> str:
            return ""

    transport = MinimalTransport()
    assert transport.name == "minimal"


@pytest.mark.asyncio
async def test_default_route_calls_send_without_context() -> None:
    class MinimalTransport(AsyncTransport):
        @property
        def name(self) -> str:
            return "minimal"

        @property
        def capabilities(self) -> TransportCapabilities:
            return TransportCapabilities()

        async def start(self) -> None: ...

        async def stop(self) -> None: ...

        async def send(self, message: str) -> None:
            self._sent = message

        async def receive(self) -> str:
            return ""

    transport = MinimalTransport()
    transport._sent = ""
    await transport.route("builder")
    assert transport._sent == "Routing to builder."


@pytest.mark.asyncio
async def test_default_route_calls_send_with_context() -> None:
    class MinimalTransport(AsyncTransport):
        @property
        def name(self) -> str:
            return "minimal"

        @property
        def capabilities(self) -> TransportCapabilities:
            return TransportCapabilities()

        async def start(self) -> None: ...

        async def stop(self) -> None: ...

        async def send(self, message: str) -> None:
            self._sent = message

        async def receive(self) -> str:
            return ""

    transport = MinimalTransport()
    transport._sent = ""
    await transport.route("planner", context="design the auth system")
    assert transport._sent == "Routing to planner.\nContext: design the auth system"


@pytest.mark.asyncio
async def test_default_route_with_none_context() -> None:
    class MinimalTransport(AsyncTransport):
        @property
        def name(self) -> str:
            return "minimal"

        @property
        def capabilities(self) -> TransportCapabilities:
            return TransportCapabilities()

        async def start(self) -> None: ...

        async def stop(self) -> None: ...

        async def send(self, message: str) -> None:
            self._sent = message

        async def receive(self) -> str:
            return ""

    transport = MinimalTransport()
    transport._sent = ""
    await transport.route("watcher", context=None)
    assert transport._sent == "Routing to watcher."
