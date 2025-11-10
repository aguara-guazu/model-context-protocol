#!/bin/bash
# Wrapper script to run manual test with proper dependencies

cd /home/user/model-context-protocol
uv run python examples/bedrock_chain_demo/manual_test.py
