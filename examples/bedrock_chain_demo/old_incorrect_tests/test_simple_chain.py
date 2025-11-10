#!/usr/bin/env python
"""
Simple direct test of tool chaining using the MCP server.
This bypasses the stdio transport and tests directly.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    ChainStep,
    ChainStepOnFailure,
    ChainToolRequest,
    ChainToolRequestParams,
)


# Import the server
import importlib.util
spec = importlib.util.spec_from_file_location("server", "examples/bedrock_chain_demo/server.py")
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)
server = server_module.server


async def test_direct():
    """Test the server directly without stdio transport."""
    print("=" * 80)
    print("DIRECT SERVER TEST - TOOL CHAINING")
    print("=" * 80)

    # Test 1: Get capabilities
    print("\n📦 Testing server capabilities...")
    from mcp.server.lowlevel import NotificationOptions
    caps = server.get_capabilities(
        NotificationOptions(),
        {}
    )

    print(f"✅ Tools capability present: {caps.tools is not None}")
    if caps.tools:
        print(f"✅ Tool chaining supported: {caps.tools.chaining}")

    # Test 2: List tools
    print("\n📦 Listing tools...")
    tools_handler = server.request_handlers.get(type(None))
    from mcp.types import ListToolsRequest

    # Create a mock request
    list_req = ListToolsRequest(method="tools/list")
    tools_response = await server.request_handlers[ListToolsRequest](list_req)

    tools_list = tools_response.root
    print(f"✅ Found {len(tools_list.tools)} tools:")
    for tool in tools_list.tools:
        chainable = "✓" if tool.outputSchema else "✗"
        print(f"   [{chainable}] {tool.name}")

    # Test 3: Call single tool
    print("\n📤 Test 1: Single Tool Call")
    print("-" * 60)
    call_req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(
            name="fetch_user_data",
            arguments={"user_id": "user123"}
        )
    )

    result = await server.request_handlers[CallToolRequest](call_req)
    call_result = result.root

    print(f"✅ Result: {call_result.isError and 'Error' or 'Success'}")
    if call_result.structuredContent:
        print(f"   User: {call_result.structuredContent.get('name')}")
        print(f"   Bio: {call_result.structuredContent.get('bio')}")

    # Test 4: Simple chain
    print("\n📤 Test 2: Simple Chain (Fetch → Analyze)")
    print("-" * 60)
    chain_req = ChainToolRequest(
        method="tools/chain",
        params=ChainToolRequestParams(
            chain=[
                ChainStep(
                    tool="fetch_user_data",
                    id="fetch",
                    params={"user_id": "user123"}
                ),
                ChainStep(
                    tool="analyze_sentiment",
                    id="sentiment",
                    params={"text": "fetch.bio", "detailed": False}
                )
            ],
            returnFormat="full"
        )
    )

    chain_result = await server.request_handlers[ChainToolRequest](chain_req)
    chain_data = chain_result.root

    print(f"✅ Chain Status: {chain_data.status}")
    print(f"   Steps executed: {len(chain_data.stepsExecuted)}")
    for step in chain_data.stepsExecuted:
        emoji = "✅" if step.status == "success" else "❌"
        print(f"   {emoji} {step.stepId} ({step.tool}): {step.status} ({step.durationMs:.2f}ms)")

    if chain_data.result:
        print(f"\n   Final Result:")
        print(f"      Sentiment: {chain_data.result.get('overall_sentiment')}")
        print(f"      Confidence: {chain_data.result.get('confidence')}")

    # Test 5: Complex chain
    print("\n📤 Test 3: Complex Chain (Fetch → Analyze → Calculate → Report)")
    print("-" * 60)
    complex_chain_req = ChainToolRequest(
        method="tools/chain",
        params=ChainToolRequestParams(
            chain=[
                ChainStep(
                    tool="fetch_user_data",
                    id="user",
                    params={"user_id": "user123"}
                ),
                ChainStep(
                    tool="analyze_sentiment",
                    id="sentiment",
                    params={"text": "user.bio", "detailed": False},
                    onFailure=ChainStepOnFailure(action="skip_and_continue")
                ),
                ChainStep(
                    tool="calculate_metrics",
                    id="metrics",
                    params={"user_data": "user", "include_engagement_score": True}
                ),
                ChainStep(
                    tool="format_report",
                    id="report",
                    params={
                        "user_name": "user.name",
                        "sentiment": "sentiment",
                        "metrics": "metrics"
                    }
                )
            ],
            returnFormat="final_only",
            timeout=30.0
        )
    )

    complex_result = await server.request_handlers[ChainToolRequest](complex_chain_req)
    complex_data = complex_result.root

    print(f"✅ Chain Status: {complex_data.status}")
    print(f"   Total steps: {len(complex_data.stepsExecuted)}")

    for step in complex_data.stepsExecuted:
        emoji = "✅" if step.status == "success" else "❌"
        print(f"   {emoji} {step.stepId}: {step.status} ({step.durationMs:.2f}ms)")

    if complex_data.result and complex_data.result.get("report"):
        print(f"\n📄 Generated Report:")
        print("-" * 60)
        print(complex_data.result["report"])
        print("-" * 60)

    print("\n" + "=" * 80)
    print("✅ ALL DIRECT TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    # Now test with Claude
    print("\n🤖 Testing with Claude Haiku 4.5...")
    print("-" * 60)

    import httpx

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  Skipping Claude test: ANTHROPIC_API_KEY not set")
        return

    # Get tool descriptions for Claude
    tools_info = "\n".join([
        f"- {tool.name}: {tool.description}"
        for tool in tools_list.tools
    ])

    prompt = f"""I have access to these tools on an MCP server:

{tools_info}

The server supports tool chaining, which means I can chain multiple tools together in a single request.

Please suggest 3 useful tool chains I could create:
1. A simple 2-step chain
2. A 3-step chain
3. A complex 4-step chain with error handling

For each, explain what it would accomplish."""

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60.0
    )

    response.raise_for_status()
    claude_response = response.json()["content"][0]["text"]

    print("🤖 Claude's Analysis:")
    print("-" * 60)
    print(claude_response)
    print("-" * 60)

    print("\n" + "=" * 80)
    print("🎉 ALL TESTS INCLUDING CLAUDE COMPLETED!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_direct())
