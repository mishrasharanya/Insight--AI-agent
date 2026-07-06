# mcp_client.py = generic MCP client for connecting to any configured MCP server.
# Not tied to Gmail/Calendar specifically - works with whatever server you
# define in mcp_config.py, since MCP is a standardized protocol.
#
# Requires: pip install mcp --break-system-packages

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_config import MCP_SERVERS


async def _list_tools_async(server_key):
    server = MCP_SERVERS[server_key]

    params = StdioServerParameters(
        command=server["command"],
        args=server.get("args", []),
        env=server.get("env", {}),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [
                {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
                for t in tools_result.tools
            ]


def list_tools(server_key):
    """
    Connects to a configured MCP server and returns its available tools.
    Run this FIRST for any new server - tool names and parameter schemas
    vary between MCP server implementations, so don't guess call_tool()
    arguments without checking this first.
    """
    if server_key not in MCP_SERVERS:
        raise ValueError(f"'{server_key}' not found in mcp_config.py MCP_SERVERS")

    return asyncio.run(_list_tools_async(server_key))


async def _call_tool_async(server_key, tool_name, tool_args):
    server = MCP_SERVERS[server_key]

    params = StdioServerParameters(
        command=server["command"],
        args=server.get("args", []),
        env=server.get("env", {}),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)

            # MCP tool results come back as a list of content blocks.
            # Most servers return one text block containing JSON - parse it
            # if possible, otherwise hand back the raw text.
            output = []
            for block in result.content:
                text = getattr(block, "text", None)
                if text is None:
                    continue
                try:
                    output.append(json.loads(text))
                except json.JSONDecodeError:
                    output.append(text)

            return output


def call_tool(server_key, tool_name, tool_args=None):
    """
    Calls a specific tool on a configured MCP server.
    tool_args should match the input_schema you saw from list_tools().
    """
    if server_key not in MCP_SERVERS:
        raise ValueError(f"'{server_key}' not found in mcp_config.py MCP_SERVERS")

    return asyncio.run(_call_tool_async(server_key, tool_name, tool_args or {}))


def main():
    """Quick manual check: list tools for every configured server."""
    for server_key in MCP_SERVERS:
        print(f"\n=== {server_key} ===")
        try:
            tools = list_tools(server_key)
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"  Could not connect: {e}")


if __name__ == "__main__":
    main()
