#!/usr/bin/env python
"""
Simple Test Script for Tool Chaining

This script demonstrates the tool chaining concept without needing
all MCP dependencies installed. It shows how the chain would work.
"""

import json


class MockChainExecutor:
    """Mock implementation showing how chain execution works."""

    def __init__(self):
        self.users_db = {
            "user123": {
                "id": "user123",
                "name": "Alice Johnson",
                "bio": "I love technology and innovation!",
                "metrics": {"posts_count": 3, "followers": 150, "following": 200},
            }
        }
        self.step_results = {}

    def resolve_reference(self, value):
        """Resolve references like 'step1.field'."""
        if isinstance(value, str):
            parts = value.split(".")
            # Check if this is a reference to a step
            if parts[0] in self.step_results:
                result = self.step_results[parts[0]]
                # If there are more parts, navigate through them
                for field in parts[1:]:
                    if isinstance(result, dict):
                        result = result.get(field)
                    else:
                        # Can't navigate further
                        break
                return result
        return value

    def fetch_user_data(self, user_id):
        """Tool 1: Fetch user data."""
        return self.users_db.get(user_id, {})

    def analyze_sentiment(self, text):
        """Tool 2: Analyze sentiment."""
        positive_words = ["love", "innovation", "excited", "amazing"]
        score = sum(word in text.lower() for word in positive_words) / 4
        return {
            "overall_sentiment": "positive" if score > 0 else "neutral",
            "confidence": round(score, 2),
        }

    def calculate_metrics(self, user_data):
        """Tool 3: Calculate metrics."""
        metrics = user_data.get("metrics", {})
        followers = metrics.get("followers", 0)
        posts = metrics.get("posts_count", 0)
        engagement_score = (followers * 2 + posts * 3) / 10
        return {
            "engagement_score": round(engagement_score, 2),
            "activity_level": "high" if posts > 5 else "medium" if posts > 2 else "low",
        }

    def format_report(self, user_name, sentiment, metrics):
        """Tool 4: Format report."""
        report = f"""# User Report: {user_name}

## Sentiment Analysis
- Overall: {sentiment.get('overall_sentiment', 'N/A')}
- Confidence: {sentiment.get('confidence', 'N/A')}

## Metrics
- Engagement Score: {metrics.get('engagement_score', 'N/A')}
- Activity Level: {metrics.get('activity_level', 'N/A')}
"""
        return {"report": report}

    def execute_tool(self, tool_name, params):
        """Execute a single tool."""
        # Resolve all parameters
        resolved_params = {}
        for key, value in params.items():
            resolved_params[key] = self.resolve_reference(value)

        # Execute the tool
        if tool_name == "fetch_user_data":
            return self.fetch_user_data(resolved_params["user_id"])
        elif tool_name == "analyze_sentiment":
            return self.analyze_sentiment(resolved_params["text"])
        elif tool_name == "calculate_metrics":
            return self.calculate_metrics(resolved_params["user_data"])
        elif tool_name == "format_report":
            return self.format_report(
                resolved_params["user_name"],
                resolved_params["sentiment"],
                resolved_params["metrics"],
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def execute_chain(self, chain_spec):
        """Execute a chain of tools."""
        print("\n" + "=" * 80)
        print("EXECUTING CHAIN")
        print("=" * 80)

        results = []

        for i, step in enumerate(chain_spec, 1):
            step_id = step["id"]
            tool_name = step["tool"]
            params = step["params"]

            print(f"\n[Step {i}/{len(chain_spec)}] {step_id}: {tool_name}")
            print(f"  Params: {json.dumps(params, indent=4)}")

            try:
                # Execute tool
                result = self.execute_tool(tool_name, params)

                # Store result for future reference
                self.step_results[step_id] = result

                print(f"  ✅ Success!")
                print(f"  Result keys: {list(result.keys())}")

                results.append(
                    {
                        "step_id": step_id,
                        "tool": tool_name,
                        "status": "success",
                        "output": result,
                    }
                )

            except Exception as e:
                print(f"  ❌ Failed: {e}")
                results.append(
                    {"step_id": step_id, "tool": tool_name, "status": "failed", "error": str(e)}
                )

        return results


def test_simple_chain():
    """Test a simple two-step chain."""
    print("\n" + "=" * 80)
    print("TEST 1: Simple Chain (Fetch → Analyze)")
    print("=" * 80)

    executor = MockChainExecutor()

    chain = [
        {"id": "fetch", "tool": "fetch_user_data", "params": {"user_id": "user123"}},
        {
            "id": "sentiment",
            "tool": "analyze_sentiment",
            "params": {"text": "fetch.bio"},  # ← Reference to previous step
        },
    ]

    results = executor.execute_chain(chain)

    print("\n📊 CHAIN RESULT:")
    for result in results:
        status_emoji = "✅" if result["status"] == "success" else "❌"
        print(f"  {status_emoji} {result['step_id']}: {result['status']}")

    final_result = results[-1]["output"]
    print(f"\n🎯 FINAL OUTPUT:")
    print(f"  Sentiment: {final_result['overall_sentiment']}")
    print(f"  Confidence: {final_result['confidence']}")


def test_complex_chain():
    """Test a complex four-step chain."""
    print("\n\n" + "=" * 80)
    print("TEST 2: Complex Chain (Fetch → Analyze → Calculate → Report)")
    print("=" * 80)

    executor = MockChainExecutor()

    chain = [
        {"id": "user", "tool": "fetch_user_data", "params": {"user_id": "user123"}},
        {
            "id": "sentiment",
            "tool": "analyze_sentiment",
            "params": {"text": "user.bio"},  # ← Reference to step 1
        },
        {
            "id": "metrics",
            "tool": "calculate_metrics",
            "params": {"user_data": "user"},  # ← Reference to step 1
        },
        {
            "id": "report",
            "tool": "format_report",
            "params": {
                "user_name": "user.name",  # ← Reference to step 1
                "sentiment": "sentiment",  # ← Reference to step 2
                "metrics": "metrics",  # ← Reference to step 3
            },
        },
    ]

    results = executor.execute_chain(chain)

    print("\n📊 CHAIN RESULT:")
    for result in results:
        status_emoji = "✅" if result["status"] == "success" else "❌"
        print(f"  {status_emoji} {result['step_id']}: {result['status']}")

    if results[-1]["status"] == "success":
        final_result = results[-1]["output"]
        print(f"\n📄 GENERATED REPORT:")
        print("-" * 80)
        print(final_result["report"])
        print("-" * 80)
    else:
        print(f"\n❌ Chain failed at step: {results[-1]['step_id']}")
        print(f"   Error: {results[-1].get('error', 'Unknown error')}")


def main():
    """Run all tests."""
    print("=" * 80)
    print("TOOL CHAINING DEMONSTRATION")
    print("=" * 80)
    print("\nThis demonstrates how tool chaining works:")
    print("  1. Each step can reference outputs from previous steps")
    print("  2. References use dot notation: 'step_id.field'")
    print("  3. The server resolves references and executes the chain")
    print("  4. Intermediate results stay server-side (not in model context)")

    test_simple_chain()
    test_complex_chain()

    print("\n\n" + "=" * 80)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("  ✅ References work: 'step1.field' gets resolved correctly")
    print("  ✅ Multi-step chains execute sequentially")
    print("  ✅ Each step can use outputs from any previous step")
    print("  ✅ No large data passed through model context")
    print("\nTo test with real MCP server, run:")
    print("  cd /home/user/model-context-protocol")
    print("  uv run python examples/bedrock_chain_demo/manual_test.py")


if __name__ == "__main__":
    main()
