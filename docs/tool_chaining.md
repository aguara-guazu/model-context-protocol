# Declarative Tool Chaining

## Overview

Declarative Tool Chaining allows models to orchestrate multiple tool calls efficiently by declaring the entire workflow upfront. The MCP server validates and executes the chain, keeping intermediate results server-side to reduce token consumption and latency.

## Key Benefits

1. **Reduced Token Usage**: Large intermediate results stay server-side instead of passing through the model's context multiple times
2. **Lower Latency**: One RPC call instead of N sequential calls
3. **Semantic Validation**: Server validates the entire chain before execution
4. **Declarative Error Handling**: Define what happens when steps fail
5. **Simpler Orchestration**: Model declares "what" to do, server handles "how"

## Basic Concepts

### Chain Structure

A chain consists of:
- **Steps**: Individual tool calls to execute in sequence
- **References**: Link outputs from previous steps to inputs of later steps
- **Error Handling**: Strategies for handling failures
- **Validation**: Optional rules for step outputs

### Reference Syntax

Use dot notation to reference previous step outputs:
- `"step_id.field_name"` - Reference a field from a previous step
- `"step_id.nested.field"` - Reference nested fields
- Literal values (strings, numbers, bools, objects) are passed as-is

## Server Implementation

### 1. Mark Tools as Chainable

Tools need an `outputSchema` to be referenced in chains:

```python
from mcp.server import Server
import mcp.types as types

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="fetch_data",
            description="Fetch data from a source",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"}
                },
                "required": ["source_id"]
            },
            outputSchema={  # Required for chaining
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "metadata": {"type": "object"}
                }
            }
        ),
        # ... more tools
    ]
```

### 2. Register Chain Handler

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle individual tool calls."""
    if name == "fetch_data":
        return {"content": "...", "metadata": {...}}
    # ... handle other tools

@server.chain_tools()
async def chain_tools(tool_name: str, arguments: dict):
    """Handle chained tool calls.

    This can re-use your call_tool logic.
    The framework handles validation and reference resolution.
    """
    return await call_tool(tool_name, arguments)
```

### 3. Server Capabilities

The server automatically advertises chaining support in its capabilities:

```python
capabilities = server.get_capabilities(
    notification_options=NotificationOptions(),
    experimental_capabilities={},
)
# capabilities.tools.chaining will be True
```

## Client Usage

### Simple Two-Step Chain

```python
from mcp.types import ChainToolRequest, ChainToolRequestParams, ChainStep

# Create a chain request
request = ChainToolRequest(
    method="tools/chain",
    params=ChainToolRequestParams(
        chain=[
            ChainStep(
                tool="fetch_data",
                id="fetch",
                params={"source_id": "abc123"}
            ),
            ChainStep(
                tool="process_data",
                id="process",
                params={
                    "content": "fetch.content",  # Reference previous step
                    "format": "json"
                }
            )
        ],
        returnFormat="final_only"
    )
)

# Execute the chain
result = await client_session.send_request(request)

# result.status: "success" | "partial_success" | "failed"
# result.result: Final output from the chain
# result.stepsExecuted: Details of all executed steps
```

### Chain with Error Handling

```python
from mcp.types import ChainStepOnFailure

ChainStep(
    tool="risky_operation",
    id="risky",
    params={...},
    onFailure=ChainStepOnFailure(
        action="return_step",  # Return output from previous step
        returnStep="previous_step"
    )
)
```

### Error Handling Strategies

- **`abort`** (default): Stop execution and return error
- **`return_step`**: Return output from a specific previous step
- **`skip_and_continue`**: Continue to the next step

### Validation Rules

```python
from mcp.types import ChainStepValidation

ChainStep(
    tool="fetch_important_data",
    id="fetch",
    params={...},
    validation=ChainStepValidation(
        requireField="data",  # Fail if output doesn't have this field
        requireNonEmpty=True   # Fail if output is empty
    )
)
```

## Complete Example

```python
# Workflow: Fetch document → Extract keywords → Format report
request = ChainToolRequest(
    method="tools/chain",
    params=ChainToolRequestParams(
        chain=[
            ChainStep(
                tool="fetch_document",
                id="doc",
                params={"doc_id": "report_2024"}
            ),
            ChainStep(
                tool="extract_keywords",
                id="keywords",
                params={
                    "text": "doc.content",
                    "max_keywords": 10
                },
                onFailure=ChainStepOnFailure(
                    action="skip_and_continue"  # Continue without keywords
                )
            ),
            ChainStep(
                tool="format_report",
                id="report",
                params={
                    "title": "doc.metadata.title",
                    "keywords": "keywords.keywords",
                    "author": "doc.metadata.author"
                }
            )
        ],
        returnFormat="full",  # Return all step results
        timeout=60.0
    )
)

result = await client_session.send_request(request)

if result.status == "success":
    print(f"Report: {result.result['report']}")

    # Inspect each step
    for step in result.stepsExecuted:
        print(f"Step {step.stepId}: {step.status} ({step.durationMs}ms)")
```

## Response Format

### ChainToolResult

```python
{
    "status": "success" | "partial_success" | "failed",
    "result": {...},  # Final result or specified step result
    "stepsExecuted": [
        {
            "stepId": "doc",
            "tool": "fetch_document",
            "status": "success",
            "durationMs": 123.45,
            "input": {"doc_id": "report_2024"},
            "output": {"content": "...", "metadata": {...}}
        },
        # ... more steps
    ],
    "error": "Error message if status is 'failed'"
}
```

## Limitations

### What Chaining Supports
- ✅ Linear workflows (step 1 → 2 → 3)
- ✅ Conditional fallbacks (if step fails, do X)
- ✅ Complex parameter mappings
- ✅ Large intermediate data handling
- ✅ Error recovery strategies

### What Chaining Doesn't Support
- ❌ Parallel execution (steps 1 & 2 simultaneously)
- ❌ Loops (iterate over results)
- ❌ Complex conditional logic (if result.x > 100, do Y)
- ❌ Arbitrary computations between steps

### Workarounds

For unsupported cases:
1. **Parallel steps**: Create a tool that does both operations server-side
2. **Loops**: Create a tool that handles iteration
3. **Complex logic**: Chain up to the decision point, let model decide next steps
4. **Computations**: Create a specialized transformation tool

## Best Practices

1. **Always provide outputSchema** for tools that will be referenced
2. **Use meaningful step IDs** for clarity
3. **Define error handling strategies** for each critical step
4. **Keep chains focused** - break very long chains into multiple requests
5. **Log chain execution** for debugging and monitoring
6. **Validate early** - the server will catch many errors before execution

## Security Considerations

- Servers can restrict which tools can be chained
- Field mappings are explicit (no implicit data flow)
- Resource limits can be enforced (timeout, max chain length)
- Server-side validation catches schema mismatches

## Performance Tips

- Chains reduce token usage by 70-95% for multi-step document workflows
- Use `returnFormat: "final_only"` to reduce response size
- Set appropriate timeouts for long-running chains
- Monitor step durations to identify bottlenecks
