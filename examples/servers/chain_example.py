#!/usr/bin/env python
"""
Example MCP server demonstrating declarative tool chaining.

This server provides tools that can be chained together to perform
multi-step operations efficiently.
"""

import asyncio

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

# Create the server
server = Server("chain-example")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="fetch_document",
            description="Fetch a document by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Document ID to fetch"},
                },
                "required": ["doc_id"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Document content"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "author": {"type": "string"},
                            "date": {"type": "string"},
                        },
                    },
                },
            },
        ),
        types.Tool(
            name="extract_keywords",
            description="Extract keywords from text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"},
                    "max_keywords": {"type": "integer", "description": "Maximum keywords to extract"},
                },
                "required": ["text"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        ),
        types.Tool(
            name="format_report",
            description="Format data into a report",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "author": {"type": "string"},
                },
                "required": ["title", "keywords"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "report": {"type": "string", "description": "Formatted report"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> dict:
    """Handle individual tool calls."""
    if name == "fetch_document":
        doc_id = arguments["doc_id"]
        # Simulate fetching a document
        return {
            "content": f"This is the content of document {doc_id}. It discusses important topics.",
            "metadata": {"author": "John Doe", "date": "2024-01-15"},
        }

    elif name == "extract_keywords":
        text = arguments["text"]
        max_keywords = arguments.get("max_keywords", 5)
        # Simple keyword extraction (in reality would use NLP)
        words = text.split()
        keywords = [w.strip(".,!?") for w in words if len(w) > 5][:max_keywords]
        return {"keywords": keywords}

    elif name == "format_report":
        title = arguments["title"]
        keywords = arguments["keywords"]
        author = arguments.get("author", "Unknown")
        report = f"# {title}\n\nAuthor: {author}\n\nKeywords: {', '.join(keywords)}\n"
        return {"report": report}

    else:
        raise ValueError(f"Unknown tool: {name}")


@server.chain_tools()
async def chain_tools(tool_name: str, arguments: dict) -> dict:
    """Handle chained tool calls.

    This re-uses the call_tool logic for execution.
    The server framework will handle validation, reference resolution,
    and error handling automatically.
    """
    return await call_tool(tool_name, arguments)


async def main():
    """Run the server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="chain-example",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=types.NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
