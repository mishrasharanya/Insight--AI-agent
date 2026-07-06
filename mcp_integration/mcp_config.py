# mcp_config.py = configuration for MCP servers you connect to.
# Add/edit entries here rather than hardcoding server details elsewhere.

MCP_SERVERS = {
    # Example: @cocal/google-calendar-mcp (Node, npx-based)
    # Setup: https://www.npmjs.com/package/@cocal/google-calendar-mcp
    # Requires: GOOGLE_OAUTH_CREDENTIALS pointing to your gcp-oauth.keys.json
    "google_calendar": {
        "command": "npx",
        "args": ["@cocal/google-calendar-mcp"],
        "env": {
            "GOOGLE_OAUTH_CREDENTIALS": "/path/to/your/gcp-oauth.keys.json"
        },
    },

    # Example: guinacio/mcp-google-calendar (pure Python, no npx needed)
    # Setup: https://github.com/guinacio/mcp-google-calendar
    # "google_calendar_python": {
    #     "command": "python",
    #     "args": ["-m", "mcp_server_google_calendar"],
    #     "env": {},
    # },

    # Example: mcp-google-workspace (Node, calendar + Gmail together)
    # Setup: https://github.com/j3k0/mcp-google-workspace
    # "google_workspace": {
    #     "command": "npx",
    #     "args": ["mcp-google-workspace"],
    #     "env": {},
    # },
}
