#!/usr/bin/env python
"""
MCP Server with Tool Chaining Support - Demo Server

This server provides multiple tools that can be chained together to perform
complex workflows. It demonstrates real-world use cases like data fetching,
text processing, translation, and storage.

Tools available:
1. fetch_user_data - Fetch user profile information
2. analyze_sentiment - Analyze sentiment of text
3. translate_text - Translate text between languages
4. generate_summary - Generate a summary from text
5. calculate_metrics - Calculate various metrics from data
6. format_report - Format data into a structured report
"""

import asyncio
import json
import logging

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the server
server = Server("bedrock-chain-demo")

# Mock database of users
USERS_DB = {
    "user123": {
        "id": "user123",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "bio": "I love technology and innovation! Always excited to learn new things.",
        "posts": [
            "Just finished an amazing project!",
            "Feeling frustrated with the slow progress today.",
            "Can't wait for the weekend!",
        ],
        "language": "en",
        "metrics": {"posts_count": 3, "followers": 150, "following": 200},
    },
    "user456": {
        "id": "user456",
        "name": "Bob Smith",
        "email": "bob@example.com",
        "bio": "Software engineer passionate about AI and machine learning.",
        "posts": [
            "Deployed a new feature today!",
            "Learning about neural networks is fascinating.",
        ],
        "language": "en",
        "metrics": {"posts_count": 2, "followers": 89, "following": 120},
    },
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List all available tools with their schemas."""
    return [
        types.Tool(
            name="fetch_user_data",
            description="Fetch complete user profile data including bio, posts, and metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID to fetch"},
                },
                "required": ["user_id"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "bio": {"type": "string"},
                    "posts": {"type": "array", "items": {"type": "string"}},
                    "language": {"type": "string"},
                    "metrics": {
                        "type": "object",
                        "properties": {
                            "posts_count": {"type": "number"},
                            "followers": {"type": "number"},
                            "following": {"type": "number"},
                        },
                    },
                },
                "required": ["id", "name", "bio", "posts"],
            },
        ),
        types.Tool(
            name="analyze_sentiment",
            description="Analyze sentiment of text and return positive/negative/neutral classification",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"},
                    "detailed": {
                        "type": "boolean",
                        "description": "Return detailed scores for each post",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "overall_sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "positive_score": {"type": "number"},
                    "negative_score": {"type": "number"},
                    "neutral_score": {"type": "number"},
                    "details": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["overall_sentiment", "confidence"],
            },
        ),
        types.Tool(
            name="translate_text",
            description="Translate text from one language to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate"},
                    "source_lang": {
                        "type": "string",
                        "description": "Source language code (e.g., 'en', 'es', 'fr')",
                    },
                    "target_lang": {
                        "type": "string",
                        "description": "Target language code (e.g., 'en', 'es', 'fr')",
                    },
                },
                "required": ["text", "target_lang"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "original_text": {"type": "string"},
                    "translated_text": {"type": "string"},
                    "source_lang": {"type": "string"},
                    "target_lang": {"type": "string"},
                },
                "required": ["translated_text"],
            },
        ),
        types.Tool(
            name="generate_summary",
            description="Generate a concise summary from longer text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to summarize"},
                    "max_length": {
                        "type": "number",
                        "description": "Maximum length of summary in words",
                        "default": 50,
                    },
                },
                "required": ["text"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "word_count": {"type": "number"},
                    "compression_ratio": {"type": "number"},
                },
                "required": ["summary"],
            },
        ),
        types.Tool(
            name="calculate_metrics",
            description="Calculate various metrics and statistics from user data",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_data": {
                        "type": "object",
                        "description": "User data object containing metrics",
                    },
                    "include_engagement_score": {
                        "type": "boolean",
                        "default": True,
                    },
                },
                "required": ["user_data"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "engagement_score": {"type": "number"},
                    "activity_level": {"type": "string"},
                    "follower_ratio": {"type": "number"},
                    "total_posts": {"type": "number"},
                },
                "required": ["engagement_score", "activity_level"],
            },
        ),
        types.Tool(
            name="format_report",
            description="Format various data into a structured markdown report",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_name": {"type": "string"},
                    "sentiment": {"type": "object", "description": "Sentiment analysis results"},
                    "metrics": {"type": "object", "description": "Calculated metrics"},
                    "summary": {"type": "string", "description": "Optional text summary"},
                },
                "required": ["user_name"],
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "report": {"type": "string", "description": "Formatted markdown report"},
                    "sections": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["report"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> dict:
    """Handle individual tool calls."""
    logger.info(f"Calling tool: {name} with arguments: {json.dumps(arguments, indent=2)}")

    if name == "fetch_user_data":
        user_id = arguments["user_id"]
        user = USERS_DB.get(user_id)

        if not user:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"User {user_id} not found")],
                isError=True,
            )

        logger.info(f"Fetched user data for {user_id}: {user['name']}")
        return user

    elif name == "analyze_sentiment":
        text = arguments["text"]
        detailed = arguments.get("detailed", False)

        # Simple sentiment analysis (mock implementation)
        positive_words = ["love", "amazing", "excited", "great", "happy", "fantastic", "excellent"]
        negative_words = ["frustrated", "slow", "angry", "sad", "terrible", "awful", "hate"]

        text_lower = text.lower()
        positive_count = sum(word in text_lower for word in positive_words)
        negative_count = sum(word in text_lower for word in negative_words)
        total = positive_count + negative_count + 1  # +1 to avoid division by zero

        positive_score = positive_count / total
        negative_score = negative_count / total
        neutral_score = 1 - (positive_score + negative_score)

        if positive_score > negative_score:
            overall = "positive"
            confidence = positive_score
        elif negative_score > positive_score:
            overall = "negative"
            confidence = negative_score
        else:
            overall = "neutral"
            confidence = neutral_score

        result = {
            "overall_sentiment": overall,
            "confidence": round(confidence, 2),
            "positive_score": round(positive_score, 2),
            "negative_score": round(negative_score, 2),
            "neutral_score": round(neutral_score, 2),
        }

        if detailed:
            # If text is a list of posts, analyze each
            try:
                posts = json.loads(text) if isinstance(text, str) and text.startswith("[") else [text]
                result["details"] = [{"post": post, "sentiment": overall} for post in posts[:3]]
            except Exception:
                result["details"] = []

        logger.info(f"Sentiment analysis result: {overall} (confidence: {confidence:.2f})")
        return result

    elif name == "translate_text":
        text = arguments["text"]
        source_lang = arguments.get("source_lang", "en")
        target_lang = arguments["target_lang"]

        # Mock translation (in reality would use a translation API)
        translations = {
            "es": {
                "hello": "hola",
                "thank you": "gracias",
                "good morning": "buenos días",
            },
            "fr": {
                "hello": "bonjour",
                "thank you": "merci",
                "good morning": "bonjour",
            },
        }

        # Simple mock: if translating to Spanish/French, add prefix
        if target_lang == "es":
            translated = f"[ES] {text}"
        elif target_lang == "fr":
            translated = f"[FR] {text}"
        else:
            translated = text

        logger.info(f"Translated text from {source_lang} to {target_lang}")
        return {
            "original_text": text,
            "translated_text": translated,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

    elif name == "generate_summary":
        text = arguments["text"]
        max_length = arguments.get("max_length", 50)

        # Simple summarization: take first N words
        words = text.split()
        summary_words = words[: min(len(words), max_length)]
        summary = " ".join(summary_words)

        if len(words) > max_length:
            summary += "..."

        compression_ratio = len(summary_words) / len(words) if words else 0

        logger.info(f"Generated summary: {len(summary_words)} words from {len(words)} words")
        return {
            "summary": summary,
            "word_count": len(summary_words),
            "compression_ratio": round(compression_ratio, 2),
        }

    elif name == "calculate_metrics":
        user_data = arguments["user_data"]
        include_engagement = arguments.get("include_engagement_score", True)

        metrics = user_data.get("metrics", {})
        posts_count = metrics.get("posts_count", 0)
        followers = metrics.get("followers", 0)
        following = metrics.get("following", 0)

        # Calculate engagement score
        engagement_score = 0
        if include_engagement:
            engagement_score = (followers * 2 + posts_count * 3) / 10

        # Calculate follower ratio
        follower_ratio = followers / following if following > 0 else 0

        # Determine activity level
        if posts_count > 5:
            activity_level = "high"
        elif posts_count > 2:
            activity_level = "medium"
        else:
            activity_level = "low"

        logger.info(f"Calculated metrics: engagement={engagement_score:.2f}, activity={activity_level}")
        return {
            "engagement_score": round(engagement_score, 2),
            "activity_level": activity_level,
            "follower_ratio": round(follower_ratio, 2),
            "total_posts": posts_count,
        }

    elif name == "format_report":
        user_name = arguments["user_name"]
        sentiment_data = arguments.get("sentiment", {})
        metrics_data = arguments.get("metrics", {})
        summary = arguments.get("summary", "")

        # Build markdown report
        report_lines = [
            f"# User Report: {user_name}",
            "",
            "## Overview",
            f"Generated on: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        sections = ["Overview"]

        if metrics_data:
            sections.append("Metrics")
            report_lines.extend(
                [
                    "## Metrics",
                    f"- Engagement Score: {metrics_data.get('engagement_score', 'N/A')}",
                    f"- Activity Level: {metrics_data.get('activity_level', 'N/A')}",
                    f"- Follower Ratio: {metrics_data.get('follower_ratio', 'N/A')}",
                    f"- Total Posts: {metrics_data.get('total_posts', 'N/A')}",
                    "",
                ]
            )

        if sentiment_data:
            sections.append("Sentiment Analysis")
            report_lines.extend(
                [
                    "## Sentiment Analysis",
                    f"- Overall Sentiment: **{sentiment_data.get('overall_sentiment', 'N/A')}**",
                    f"- Confidence: {sentiment_data.get('confidence', 'N/A')}",
                    f"- Positive Score: {sentiment_data.get('positive_score', 'N/A')}",
                    f"- Negative Score: {sentiment_data.get('negative_score', 'N/A')}",
                    "",
                ]
            )

        if summary:
            sections.append("Summary")
            report_lines.extend(["## Summary", summary, ""])

        report = "\n".join(report_lines)
        logger.info(f"Formatted report with {len(sections)} sections")

        return {"report": report, "sections": sections}

    else:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
            isError=True,
        )


@server.chain_tools()
async def chain_tools(tool_name: str, arguments: dict) -> dict:
    """
    Handle chained tool calls.

    This re-uses the call_tool logic for execution.
    The server framework handles:
    - Validation of the entire chain
    - Reference resolution (e.g., "step1.field")
    - Error handling strategies
    - Keeping intermediate results server-side
    """
    logger.info(f"🔗 Chain executor calling: {tool_name}")
    return await call_tool(tool_name, arguments)


async def main():
    """Run the server."""
    logger.info("=" * 60)
    logger.info("Starting MCP Server with Tool Chaining Support")
    logger.info("=" * 60)
    logger.info("Available users in database:")
    for user_id, user in USERS_DB.items():
        logger.info(f"  - {user_id}: {user['name']}")
    logger.info("=" * 60)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bedrock-chain-demo",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
