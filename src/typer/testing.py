# mypy: ignore-errors
import contextlib
import io


class Result:
    def __init__(self, exit_code, output):
        self.exit_code = exit_code
        self.output = output
        self.stdout = output


class CliRunner:
    def invoke(self, app, args, catch_exceptions=True):
        buf = io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buf):
                if not args or args[0] == "--help":
                    print(app.help)
                    print("Commands:")
                    [print(k) for k in app.commands]
                elif args[0] in app.commands:
                    app.commands[args[0]](*args[1:])
                else:
                    code = 2
                    print(f"No such command: {args[0]}")
        except Exception as e:
            if not catch_exceptions:
                raise
            code = 1
            print(str(e), file=buf)
        return Result(code, buf.getvalue())
