"""Plugin authoring contract:

A plugin is a Python package placed under ~/.local/share/godsapp/plugins/<name>/.
Its top-level __init__.py must import the Tool subclasses it contributes and
register them via ``godsapp.tools.registry.registry.register(MyTool())``.

Example:

    # ~/.local/share/godsapp/plugins/awesome_tool/__init__.py
    from godsapp.tools.base import Tool, ToolResult
    from godsapp.tools.registry import registry

    class AwesomeTool(Tool):
        name = "awesome"
        title = "Awesome scanner"
        category = "recon"
        async def run(self, target, args, *, on_stdout, on_stderr):
            on_stdout(f"scanning {target}…\\n")
            return ToolResult(exit_code=0, findings=[])

    registry.register(AwesomeTool())
"""
