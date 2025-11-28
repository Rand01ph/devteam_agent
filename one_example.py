
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk import tool, create_sdk_mcp_server

async def main():

    @tool("add", "Add two numbers", {"a": float, "b": float})
    async def add(args):
        return {
            "content": [{
                "type": "text",
                "text": f"Sum: {args['a'] + args['b']}"
            }]
        }

    @tool("multiply", "Multiply two numbers", {"a": float, "b": float})
    async def multiply(args):
        return {
            "content": [{
                "type": "text",
                "text": f"Product: {args['a'] * args['b']}"
            }]
        }

    calculator = create_sdk_mcp_server(
        name="calculator",
        version="2.0.0",
        tools=[add, multiply]  # Pass decorated functions
    )

    # Use with Claude
    options = ClaudeAgentOptions(
        mcp_servers={"calc": calculator},
        allowed_tools=["mcp__calc__add", "mcp__calc__multiply"]
    )

    async with ClaudeSDKClient() as client:
        await client.query("please tell me 3 + 1111 = ?")

        async for message in client.receive_response():
            print(message)


asyncio.run(main())