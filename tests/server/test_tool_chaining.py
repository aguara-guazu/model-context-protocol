"""Tests for declarative tool chaining functionality."""

import anyio
import pytest

from mcp.client.session import ClientSession
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.session import ServerSession
from mcp.shared.message import SessionMessage
from mcp.shared.session import RequestResponder
from mcp.types import (
    CallToolResult,
    ChainStep,
    ChainToolRequest,
    ChainToolRequestParams,
    ClientResult,
    ServerNotification,
    ServerRequest,
    TextContent,
    Tool,
)


@pytest.mark.anyio
async def test_basic_tool_chain():
    """Test a simple two-step tool chain."""
    server = Server("test")

    # Register tools
    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="get_data",
                description="Get some data",
                inputSchema={
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                },
                outputSchema={
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "count": {"type": "number"},
                    },
                },
            ),
            Tool(
                name="process_data",
                description="Process data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"},
                        "multiplier": {"type": "number"},
                    },
                    "required": ["input", "multiplier"],
                },
                outputSchema={
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "get_data":
            return {"value": f"data_{arguments['key']}", "count": 42}
        elif name == "process_data":
            return {"result": f"{arguments['input']}_processed_{arguments['multiplier']}"}
        else:
            return CallToolResult(content=[TextContent(type="text", text="Unknown tool")], isError=True)

    @server.chain_tools()
    async def chain_tools(tool_name: str, arguments: dict):
        # Re-use call_tool logic
        return await call_tool(tool_name, arguments)

    chain_result = None
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[SessionMessage](10)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[SessionMessage](10)

    # Message handler for client
    async def message_handler(
        message: RequestResponder[ServerRequest, ClientResult] | ServerNotification | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

    # Server task
    async def run_server():
        async with ServerSession(
            client_to_server_receive,
            server_to_client_send,
            InitializationOptions(
                server_name="test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        ) as server_session:
            async with anyio.create_task_group() as tg:

                async def handle_messages():
                    async for msg in server_session.incoming_messages:
                        await server._handle_message(msg, server_session, {}, False)

                tg.start_soon(handle_messages)
                await anyio.sleep_forever()

    # Run the test
    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)

        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            message_handler=message_handler,
        ) as client_session:
            # Initialize the session
            await client_session.initialize()

            # Execute chain
            chain_request = ChainToolRequest(
                method="tools/chain",
                params=ChainToolRequestParams(
                    chain=[
                        ChainStep(tool="get_data", id="step1", params={"key": "test"}),
                        ChainStep(
                            tool="process_data",
                            id="step2",
                            params={"input": "step1.value", "multiplier": 2},
                        ),
                    ],
                    returnFormat="final_only",
                ),
            )

            chain_result = await client_session.send_request(chain_request, result_type=type(None))

            # Cancel the server task
            tg.cancel_scope.cancel()

    # Verify results
    assert chain_result is not None
    assert chain_result.status == "success"
    assert chain_result.result is not None
    assert chain_result.result["result"] == "data_test_processed_2"
    assert len(chain_result.stepsExecuted) == 2


@pytest.mark.anyio
async def test_chain_with_failure_handling():
    """Test chain error handling with onFailure strategies."""
    server = Server("test")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="step1",
                description="First step",
                inputSchema={"type": "object", "properties": {}},
                outputSchema={"type": "object", "properties": {"data": {"type": "string"}}},
            ),
            Tool(
                name="step2_fail",
                description="This will fail",
                inputSchema={"type": "object", "properties": {"input": {"type": "string"}}},
                outputSchema={"type": "object", "properties": {"result": {"type": "string"}}},
            ),
            Tool(
                name="step3",
                description="Should not be reached",
                inputSchema={"type": "object", "properties": {}},
                outputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "step1":
            return {"data": "step1_output"}
        elif name == "step2_fail":
            return CallToolResult(content=[TextContent(type="text", text="Intentional failure")], isError=True)
        elif name == "step3":
            return {"final": "should_not_reach"}
        return CallToolResult(content=[TextContent(type="text", text="Unknown tool")], isError=True)

    @server.chain_tools()
    async def chain_tools(tool_name: str, arguments: dict):
        return await call_tool(tool_name, arguments)

    chain_result = None
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[SessionMessage](10)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[SessionMessage](10)

    async def message_handler(
        message: RequestResponder[ServerRequest, ClientResult] | ServerNotification | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

    async def run_server():
        async with ServerSession(
            client_to_server_receive,
            server_to_client_send,
            InitializationOptions(
                server_name="test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        ) as server_session:
            async with anyio.create_task_group() as tg:

                async def handle_messages():
                    async for msg in server_session.incoming_messages:
                        await server._handle_message(msg, server_session, {}, False)

                tg.start_soon(handle_messages)
                await anyio.sleep_forever()

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)

        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            message_handler=message_handler,
        ) as client_session:
            await client_session.initialize()

            # Test abort on failure (default behavior)
            from mcp.types import ChainStepOnFailure

            chain_request = ChainToolRequest(
                method="tools/chain",
                params=ChainToolRequestParams(
                    chain=[
                        ChainStep(tool="step1", id="s1", params={}),
                        ChainStep(
                            tool="step2_fail",
                            id="s2",
                            params={"input": "s1.data"},
                            onFailure=ChainStepOnFailure(action="abort"),
                        ),
                        ChainStep(tool="step3", id="s3", params={}),
                    ],
                ),
            )

            chain_result = await client_session.send_request(chain_request, result_type=type(None))

            tg.cancel_scope.cancel()

    # Verify that chain failed and step3 was not executed
    assert chain_result is not None
    assert chain_result.status == "failed"
    assert len(chain_result.stepsExecuted) == 2  # Only s1 and s2
    assert chain_result.stepsExecuted[0].status == "success"
    assert chain_result.stepsExecuted[1].status == "failed"


@pytest.mark.anyio
async def test_chain_validation():
    """Test chain validation catches errors before execution."""
    server = Server("test")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="valid_tool",
                description="A valid tool",
                inputSchema={"type": "object", "properties": {}},
                outputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        return {}

    @server.chain_tools()
    async def chain_tools(tool_name: str, arguments: dict):
        return await call_tool(tool_name, arguments)

    chain_result = None
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[SessionMessage](10)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[SessionMessage](10)

    async def message_handler(
        message: RequestResponder[ServerRequest, ClientResult] | ServerNotification | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

    async def run_server():
        async with ServerSession(
            client_to_server_receive,
            server_to_client_send,
            InitializationOptions(
                server_name="test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        ) as server_session:
            async with anyio.create_task_group() as tg:

                async def handle_messages():
                    async for msg in server_session.incoming_messages:
                        await server._handle_message(msg, server_session, {}, False)

                tg.start_soon(handle_messages)
                await anyio.sleep_forever()

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)

        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            message_handler=message_handler,
        ) as client_session:
            await client_session.initialize()

            # Try to use a tool that doesn't exist
            chain_request = ChainToolRequest(
                method="tools/chain",
                params=ChainToolRequestParams(
                    chain=[
                        ChainStep(tool="nonexistent_tool", id="s1", params={}),
                    ],
                ),
            )

            chain_result = await client_session.send_request(chain_request, result_type=type(None))

            tg.cancel_scope.cancel()

    # Verify validation error was caught
    assert chain_result is not None
    assert chain_result.status == "failed"
    assert "validation error" in chain_result.error.lower() or "not found" in chain_result.error.lower()


@pytest.mark.anyio
async def test_capabilities_with_chaining():
    """Test that server capabilities correctly advertise chaining support."""
    server = Server("test")

    @server.list_tools()
    async def list_tools():
        return []

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        return {}

    @server.chain_tools()
    async def chain_tools(tool_name: str, arguments: dict):
        return await call_tool(tool_name, arguments)

    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream[SessionMessage](10)
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream[SessionMessage](10)

    async def message_handler(
        message: RequestResponder[ServerRequest, ClientResult] | ServerNotification | Exception,
    ) -> None:
        if isinstance(message, Exception):
            raise message

    async def run_server():
        async with ServerSession(
            client_to_server_receive,
            server_to_client_send,
            InitializationOptions(
                server_name="test-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        ) as server_session:
            async with anyio.create_task_group() as tg:

                async def handle_messages():
                    async for msg in server_session.incoming_messages:
                        await server._handle_message(msg, server_session, {}, False)

                tg.start_soon(handle_messages)
                await anyio.sleep_forever()

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_server)

        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            message_handler=message_handler,
        ) as client_session:
            init_result = await client_session.initialize()

            # Verify chaining capability is advertised
            assert init_result.capabilities.tools is not None
            assert init_result.capabilities.tools.chaining is True

            tg.cancel_scope.cancel()
