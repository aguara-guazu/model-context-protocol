#!/usr/bin/env python
"""
Real test where Claude receives MCP tools and decides whether to chain them.

This test demonstrates the CORRECT way to use tool chaining:
1. Server exposes tools via MCP (including chain_tools)
2. Client gets all tools from server
3. Client passes tools to Claude
4. Claude DECIDES whether to use individual tools or chain them
5. Client executes Claude's decision
6. No hardcoded chains - Claude is in control
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_mcp_client():
    """Connect to the MCP server via stdio."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-u", "examples/bedrock_chain_demo/server.py"],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def format_tool_for_claude(tool) -> dict:
    """Format an MCP tool for Claude's API."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema or {},
    }


async def call_claude(api_key: str, tools: list[dict], user_message: str) -> dict:
    """Call Claude with the available tools."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 4096,
                "tools": tools,
                "messages": [{"role": "user", "content": user_message}],
            },
        )
        response.raise_for_status()
        return response.json()


async def execute_tool_call(session: ClientSession, tool_name: str, tool_input: dict) -> dict:
    """Execute a tool call via MCP."""
    logger.info(f"Executing tool: {tool_name}")
    logger.info(f"Input: {json.dumps(tool_input, indent=2)}")

    result = await session.call_tool(tool_name, tool_input)

    # Extract content from result
    if hasattr(result, "content") and result.content:
        # If it's a list of content items, extract text/data
        content = result.content[0]
        if hasattr(content, "text"):
            return json.loads(content.text) if content.text.startswith("{") else {"text": content.text}
    # If result is already a dict, return it
    return result if isinstance(result, dict) else {"result": str(result)}


async def main():
    """Run the real test with Claude deciding."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        return

    logger.info("=" * 80)
    logger.info("REAL TEST: Claude Decides Whether to Chain Tools")
    logger.info("=" * 80)

    async with get_mcp_client() as session:
        # Step 1: Get all available tools from MCP server
        logger.info("\n📋 Step 1: Getting tools from MCP server...")
        tools_response = await session.list_tools()
        mcp_tools = tools_response.tools

        logger.info(f"✅ Received {len(mcp_tools)} tools from server:")
        for tool in mcp_tools:
            logger.info(f"  - {tool.name}: {tool.description[:80] if tool.description else 'No description'}...")

        # Step 2: Format tools for Claude
        claude_tools = [format_tool_for_claude(tool) for tool in mcp_tools]

        # Step 3: Ask Claude to perform a multi-step task
        logger.info("\n🤖 Step 2: Asking Claude to perform a multi-step task...")
        user_question = (
            "I need you to fetch user data for user123, analyze the sentiment of their bio, "
            "and calculate their engagement metrics. Please help me with this."
        )
        logger.info(f"Question: {user_question}")

        claude_response = await call_claude(api_key, claude_tools, user_question)

        logger.info(f"\n📥 Claude's response:")
        logger.info(f"Stop reason: {claude_response.get('stop_reason')}")

        # Step 4: Check what Claude decided to do
        if claude_response.get("stop_reason") == "tool_use":
            tool_uses = [block for block in claude_response.get("content", []) if block.get("type") == "tool_use"]

            logger.info(f"\n🔧 Claude decided to use {len(tool_uses)} tool call(s):")
            for i, tool_use in enumerate(tool_uses, 1):
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]

                logger.info(f"\n  [{i}] Tool: {tool_name}")

                if tool_name == "chain_tools":
                    logger.info("     🎉 CLAUDE CHOSE TO CHAIN TOOLS!")
                    chain = tool_input.get("chain", [])
                    logger.info(f"     Chain has {len(chain)} steps:")
                    for j, step in enumerate(chain, 1):
                        logger.info(f"       {j}. {step['id']}: {step['tool']} <- {step['params']}")
                else:
                    logger.info(f"     Individual tool call")
                    logger.info(f"     Input: {json.dumps(tool_input, indent=6)}")

            # Step 5: Execute Claude's decision
            logger.info("\n⚙️  Step 3: Executing Claude's tool calls...")
            tool_results = []

            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_use_id = tool_use["id"]

                try:
                    result = await execute_tool_call(session, tool_name, tool_input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": tool_use_id, "content": json.dumps(result)}
                    )
                    logger.info(f"✅ {tool_name} completed")

                    # Show chain result details if it was a chain
                    if tool_name == "chain_tools" and isinstance(result, dict):
                        logger.info(f"\n📊 Chain Execution Results:")
                        logger.info(f"   Status: {result.get('status')}")
                        if result.get("stepsExecuted"):
                            logger.info(f"   Steps executed: {len(result['stepsExecuted'])}")
                            for step_result in result["stepsExecuted"]:
                                status_emoji = "✅" if step_result["status"] == "success" else "❌"
                                logger.info(
                                    f"     {status_emoji} {step_result['stepId']}: "
                                    f"{step_result['status']} ({step_result.get('executionTime', 0):.2f}ms)"
                                )
                        if result.get("result"):
                            logger.info(f"\n   Final Result:")
                            logger.info(f"   {json.dumps(result['result'], indent=6)}")

                except Exception as e:
                    logger.exception(f"❌ Error executing {tool_name}")
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": tool_use_id, "content": f"Error: {e}", "is_error": True}
                    )

            # Step 6: Get Claude's final response
            logger.info("\n🤖 Step 4: Getting Claude's final response...")
            final_response = await call_claude(
                api_key,
                claude_tools,
                user_question,  # Original message
            )

            # Build conversation with tool results
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 4096,
                        "tools": claude_tools,
                        "messages": [
                            {"role": "user", "content": user_question},
                            {"role": "assistant", "content": claude_response["content"]},
                            {"role": "user", "content": tool_results},
                        ],
                    },
                )
                response.raise_for_status()
                final_response = response.json()

            # Show Claude's final answer
            final_text = ""
            for block in final_response.get("content", []):
                if block.get("type") == "text":
                    final_text += block["text"]

            if final_text:
                logger.info("\n💬 Claude's Final Answer:")
                logger.info(f"{final_text}")

        else:
            logger.info(f"\n💬 Claude responded with text (no tool use):")
            for block in claude_response.get("content", []):
                if block.get("type") == "text":
                    logger.info(f"{block['text']}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ TEST COMPLETE")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
