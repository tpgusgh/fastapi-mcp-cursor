from fastmcp import FastMCP

mcp = FastMCP("Demo Server")

@mcp.tool
def echo(msg: str):
    return msg
