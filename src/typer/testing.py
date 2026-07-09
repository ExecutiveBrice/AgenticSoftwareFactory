import contextlib
import io
from collections.abc import Sequence

from typer import Typer


class Result:
    def __init__(self, exit_code: int, output: str) -> None:
        self.exit_code = exit_code
        self.output = output
        self.stdout = output


class CliRunner:
    def invoke(self, app: Typer, args: Sequence[str], catch_exceptions: bool = True) -> Result:
        buf = io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf):
                if not args or args[0] == "--help":
                    print(app.help)
                    print("Commands:")
                    for command_name in app.commands:
                        print(command_name)
                elif args[0] in app.commands:
                    app.commands[args[0]](*args[1:])
                else:
                    code = 2
                    print(f"No such command: {args[0]}")
        except Exception as exc:
            if not catch_exceptions:
                raise
            code = 1
            print(str(exc), file=buf)
        return Result(code, buf.getvalue())
