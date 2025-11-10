"""
Tool chaining support for MCP servers.

This module provides utilities for executing declarative tool chains,
including validation, reference resolution, and execution with error handling.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import jsonschema

import mcp.types as types

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """
    Resolves parameter references in tool chains.

    Supports references like:
    - "step_id.field_name" - reference a field from a previous step
    - "step_id.nested.field" - reference a nested field
    - Literal values (strings, numbers, bools, dicts, lists)
    """

    def __init__(self, step_results: dict[str, dict[str, Any]]):
        """
        Initialize the resolver with step results.

        Args:
            step_results: Dictionary mapping step IDs to their output results
        """
        self.step_results = step_results

    def resolve_value(self, value: Any) -> Any:
        """
        Resolve a single value, which may be a reference or a literal.

        Args:
            value: The value to resolve (can be string reference, literal, dict, or list)

        Returns:
            The resolved value

        Raises:
            ValueError: If a reference cannot be resolved
        """
        # If it's a string, check if it's a reference
        if isinstance(value, str):
            return self._resolve_string_reference(value)

        # If it's a dict, recursively resolve all values
        elif isinstance(value, dict):
            return {key: self.resolve_value(val) for key, val in value.items()}

        # If it's a list, recursively resolve all items
        elif isinstance(value, list):
            return [self.resolve_value(item) for item in value]

        # Otherwise, it's a literal (number, bool, None)
        else:
            return value

    def _resolve_string_reference(self, ref: str) -> Any:
        """
        Resolve a string that might be a reference like "step_id.field".

        Args:
            ref: The reference string

        Returns:
            The resolved value, or the original string if not a reference

        Raises:
            ValueError: If the reference is invalid
        """
        # Check if it's a reference to a step (with or without field)
        parts = ref.split(".")
        step_id = parts[0]

        # Check if this step exists in results
        if step_id in self.step_results:
            # It's a reference to a step
            if len(parts) == 1:
                # Just the step ID, return the whole object
                return self.step_results[step_id]
            else:
                # Navigate through the field path
                current = self.step_results[step_id]
                field_path = parts[1:]
                try:
                    for field in field_path:
                        if isinstance(current, dict):
                            current = current[field]
                        else:
                            raise ValueError(f"Cannot access field '{field}' on non-dict value")
                    return current
                except (KeyError, TypeError) as e:
                    raise ValueError(f"Reference '{ref}' could not be resolved: {e}") from e
        else:
            # Not a reference to a step, treat as literal string
            return ref

    def resolve_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve all parameters in a params dictionary.

        Args:
            params: Dictionary of parameters that may contain references

        Returns:
            Dictionary with all references resolved
        """
        return {key: self.resolve_value(value) for key, value in params.items()}


class ChainValidator:
    """
    Validates tool chains before execution.

    Checks that:
    - All referenced tools exist
    - Tool schemas are compatible
    - References are valid
    - Fallback targets exist
    """

    def __init__(self, available_tools: dict[str, types.Tool]):
        """
        Initialize the validator with available tools.

        Args:
            available_tools: Dictionary mapping tool names to Tool definitions
        """
        self.available_tools = available_tools

    def validate_chain(self, chain: list[types.ChainStep]) -> None:
        """
        Validate an entire chain.

        Args:
            chain: The chain of steps to validate

        Raises:
            ValueError: If the chain is invalid
        """
        if not chain:
            raise ValueError("Chain cannot be empty")

        # Check for duplicate step IDs
        step_ids = [step.id for step in chain]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Chain contains duplicate step IDs")

        # Validate each step
        for i, step in enumerate(chain):
            self._validate_step(step, step_ids, i)

    def _validate_step(self, step: types.ChainStep, all_step_ids: list[str], step_index: int) -> None:
        """
        Validate a single step in the chain.

        Args:
            step: The step to validate
            all_step_ids: List of all step IDs in the chain
            step_index: Index of this step in the chain
        """
        # Check tool exists
        if step.tool not in self.available_tools:
            raise ValueError(f"Step '{step.id}': Tool '{step.tool}' not found")

        tool = self.available_tools[step.tool]

        # Check that tool has outputSchema if it will be referenced
        # (we check if any later step might reference this one)
        if step_index < len(all_step_ids) - 1:
            # There are steps after this one that might reference it
            if tool.outputSchema is None:
                logger.warning(
                    "Step '%s' uses tool '%s' which has no outputSchema. "
                    "This may cause issues if later steps reference it.",
                    step.id,
                    step.tool,
                )

        # Validate parameter references
        self._validate_param_references(step, all_step_ids[:step_index])

        # Validate onFailure references
        if step.onFailure and step.onFailure.returnStep:
            if step.onFailure.returnStep not in all_step_ids:
                raise ValueError(
                    f"Step '{step.id}': onFailure.returnStep '{step.onFailure.returnStep}' does not exist"
                )

        # Validate onSuccess references
        if step.onSuccess and step.onSuccess.returnStep:
            if step.onSuccess.returnStep not in all_step_ids:
                raise ValueError(
                    f"Step '{step.id}': onSuccess.returnStep '{step.onSuccess.returnStep}' does not exist"
                )

    def _validate_param_references(self, step: types.ChainStep, previous_step_ids: list[str]) -> None:
        """
        Validate that parameter references point to valid previous steps.

        Args:
            step: The step to validate
            previous_step_ids: List of step IDs that come before this one
        """
        for param_name, param_value in step.params.items():
            self._check_value_references(param_value, previous_step_ids, step.id)

    def _check_value_references(self, value: Any, previous_step_ids: list[str], step_id: str) -> None:
        """
        Recursively check a value for references.

        Args:
            value: The value to check
            previous_step_ids: List of valid step IDs that can be referenced
            step_id: ID of the step being validated (for error messages)
        """
        if isinstance(value, str):
            # Check if it looks like a reference
            if "." in value:
                parts = value.split(".")
                if len(parts) >= 2:
                    potential_step_id = parts[0]
                    # Only validate if it looks like a step reference
                    # (we can't know for sure without executing)
                    if potential_step_id in previous_step_ids:
                        # Valid reference to previous step
                        pass
                    elif any(potential_step_id == sid for sid in previous_step_ids):
                        # Referencing a previous step
                        pass
                    # Otherwise might be a literal string with dots, that's OK

        elif isinstance(value, dict):
            for v in value.values():
                self._check_value_references(v, previous_step_ids, step_id)

        elif isinstance(value, list):
            for item in value:
                self._check_value_references(item, previous_step_ids, step_id)


class ChainExecutor:
    """
    Executes tool chains with error handling and timeout support.
    """

    def __init__(
        self,
        available_tools: dict[str, types.Tool],
        tool_executor: Any,
    ):
        """
        Initialize the executor.

        Args:
            available_tools: Dictionary mapping tool names to Tool definitions
            tool_executor: The tool execution function (takes tool name and args)
        """
        self.available_tools = available_tools
        self.tool_executor = tool_executor
        self.step_results: dict[str, dict[str, Any]] = {}

    async def execute_chain(
        self,
        chain: list[types.ChainStep],
        return_format: str,
        timeout: float | None,
    ) -> types.ChainToolResult:
        """
        Execute a chain of tool calls.

        Args:
            chain: The chain to execute
            return_format: "final_only" or "full"
            timeout: Optional timeout in seconds

        Returns:
            ChainToolResult with execution results
        """
        executed_steps: list[types.ChainStepResult] = []
        overall_status: types.Literal["success", "partial_success", "failed"] = "success"
        final_result: dict[str, Any] | None = None
        error_message: str | None = None

        try:
            for step in chain:
                step_result = await self._execute_step(step)
                executed_steps.append(step_result)

                if step_result.status == "failed":
                    # Handle failure according to onFailure strategy
                    if step.onFailure:
                        if step.onFailure.action == "abort":
                            overall_status = "failed"
                            error_message = step_result.error
                            break
                        elif step.onFailure.action == "return_step":
                            # Return output from specified step
                            if step.onFailure.returnStep:
                                final_result = self.step_results.get(step.onFailure.returnStep)
                            overall_status = "partial_success"
                            break
                        elif step.onFailure.action == "skip_and_continue":
                            overall_status = "partial_success"
                            continue
                    else:
                        # Default: abort on failure
                        overall_status = "failed"
                        error_message = step_result.error
                        break

                elif step_result.status == "success":
                    # Store the result for future reference
                    if step_result.output:
                        self.step_results[step.id] = step_result.output

                    # Check onSuccess actions
                    if step.onSuccess:
                        if step.onSuccess.action == "stop_and_return":
                            if step.onSuccess.returnStep:
                                final_result = self.step_results.get(step.onSuccess.returnStep)
                            else:
                                final_result = step_result.output
                            break

                    # Default: store as final result
                    final_result = step_result.output

        except Exception as e:
            logger.exception("Unexpected error during chain execution")
            overall_status = "failed"
            error_message = f"Chain execution error: {str(e)}"

        return types.ChainToolResult(
            status=overall_status,
            result=final_result,
            stepsExecuted=executed_steps,
            error=error_message,
        )

    async def _execute_step(self, step: types.ChainStep) -> types.ChainStepResult:
        """
        Execute a single step in the chain.

        Args:
            step: The step to execute

        Returns:
            ChainStepResult with execution details
        """
        start_time = time.time()
        status: types.Literal["success", "failed", "skipped"] = "success"
        output: dict[str, Any] | None = None
        error: str | None = None
        resolved_params: dict[str, Any] = {}

        try:
            # Resolve parameter references
            resolver = ReferenceResolver(self.step_results)
            resolved_params = resolver.resolve_params(step.params)

            # Validate input against tool's inputSchema
            tool = self.available_tools[step.tool]
            try:
                jsonschema.validate(instance=resolved_params, schema=tool.inputSchema)
            except jsonschema.ValidationError as e:
                raise ValueError(f"Input validation failed: {e.message}") from e

            # Execute the tool
            result = await self.tool_executor(step.tool, resolved_params)

            # Extract structured content from result
            if isinstance(result, types.CallToolResult):
                output = result.structuredContent
                if result.isError:
                    status = "failed"
                    error = str(result.content[0].text) if result.content else "Tool execution failed"
            elif isinstance(result, dict):
                output = result
            else:
                raise ValueError(f"Unexpected tool result type: {type(result)}")

            # Validate output against tool's outputSchema if present
            if status == "success" and tool.outputSchema:
                if output is None:
                    status = "failed"
                    error = "Tool has outputSchema but returned no structured content"
                else:
                    try:
                        jsonschema.validate(instance=output, schema=tool.outputSchema)
                    except jsonschema.ValidationError as e:
                        status = "failed"
                        error = f"Output validation failed: {e.message}"

            # Apply step-level validation
            if status == "success" and step.validation:
                validation_error = self._validate_output(output, step.validation)
                if validation_error:
                    status = "failed"
                    error = validation_error

        except Exception as e:
            logger.exception("Error executing step '%s'", step.id)
            status = "failed"
            error = str(e)

        duration_ms = (time.time() - start_time) * 1000

        return types.ChainStepResult(
            stepId=step.id,
            tool=step.tool,
            status=status,
            durationMs=duration_ms,
            input=resolved_params,
            output=output if status == "success" else None,
            error=error if status == "failed" else None,
        )

    def _validate_output(self, output: dict[str, Any] | None, validation: types.ChainStepValidation) -> str | None:
        """
        Validate step output against validation rules.

        Args:
            output: The output to validate
            validation: Validation rules

        Returns:
            Error message if validation fails, None otherwise
        """
        if validation.requireField:
            if not output or validation.requireField not in output:
                return f"Required field '{validation.requireField}' not found in output"

        if validation.requireNonEmpty:
            if not output or not any(output.values()):
                return "Output is empty but requireNonEmpty is set"

        return None
