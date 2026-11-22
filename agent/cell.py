"""What a runtime needs to know about one cell, as paths on the host and as paths inside its sandbox."""
import os
from dataclasses import dataclass
from pathlib import Path


def resolve(path):
    return os.path.realpath(path) if path else ""


@dataclass(frozen=True)
class Cell:
    name: str
    runtime: str
    state: Path          # host: $CELLS_HOME/screens/NAME/state
    home: Path           # host: the cell's home, mounted at sandbox_home
    sandbox_home: str    # sandbox: $HOME
    inner: str           # sandbox: $HOME/.cell (state, knowledge and helper commands)
    display: str
    owner: str
    node: str
    chrome_wrapper: str  # sandbox path of bin/cell-chrome
    playwright_mcp: str
    opencontext: str
    instructions: str

    @property
    def config_dir(self):
        """Host path for runtime config files; the same folder is $HOME/.cell/config inside."""
        return self.home / ".cell" / "config"

    @classmethod
    def load(cls, name):
        env = os.environ
        cell_dir = Path(env["CELLS_HOME"]) / "screens" / name
        state = cell_dir / "state"
        sandbox_home = os.path.expanduser("~")
        inner = f"{sandbox_home}/.cell"
        display = f":{(cell_dir / 'display').read_text().strip()}"
        owner = env.get("CELLS_OWNER") or "the operator"
        text = (Path(env["CELLS_APP"]) / "share" / "instructions.md").read_text()
        for key, value in (("@NAME@", name), ("@DISPLAY@", display), ("@OWNER@", owner)):
            text = text.replace(key, value)
        runtime_file = state / "runtime"
        opencontext = env.get("CELLS_OPENCONTEXT", "")
        return cls(
            name=name,
            runtime=runtime_file.read_text().strip() if runtime_file.exists() else "claude",
            state=state,
            home=cell_dir / "home",
            sandbox_home=sandbox_home,
            inner=inner,
            display=display,
            owner=owner,
            node=resolve(env.get("CELLS_NODE")),
            chrome_wrapper=f"{inner}/bin/cell-chrome",
            playwright_mcp=env.get("CELLS_PLAYWRIGHT_MCP", ""),
            opencontext=opencontext if opencontext and os.path.isfile(opencontext) else "",
            instructions=text,
        )

    def playwright_args(self):
        return [self.playwright_mcp, "--executable-path", self.chrome_wrapper, "--no-sandbox",
                "--user-data-dir", f"{self.sandbox_home}/chrome-profile", "--output-dir", f"{self.sandbox_home}/playwright"]

    def sandbox_env(self):
        """The environment every runtime starts with inside the sandbox. Nothing secret."""
        path = ":".join([f"{self.inner}/bin", os.path.dirname(self.node), "/usr/local/bin", "/usr/bin", "/bin"])
        return {
            "HOME": self.sandbox_home,
            "USER": os.environ.get("USER", ""),
            "LANG": "C.UTF-8",
            "PATH": path,
            "DISPLAY": self.display,
            "XAUTHORITY": f"{self.sandbox_home}/.Xauthority",
            "CELL_NAME": self.name,
            "CELL_STATE": f"{self.inner}/state",
            "CELLS_OWNER": self.owner,
            "CELLS_CHROME_BIN": resolve(os.environ.get("CELLS_CHROME_BIN")),
            "CELLS_KNOWLEDGE": f"{self.inner}/knowledge/contexts",
            "OPENCONTEXT_ROOT": f"{self.inner}/knowledge",
            "OPENCONTEXT_CONTEXTS_ROOT": f"{self.inner}/knowledge/contexts",
        }
