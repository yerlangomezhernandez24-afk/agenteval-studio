"""Explicit test-only server: installed wheel + synthetic loopback HTTP double."""

import sys
from pathlib import Path

import uvicorn
from ollama_double import serve_double

from agenteval.api import create_app
from agenteval.ollama import OllamaClient

if __name__ == "__main__":
    with serve_double() as (state, port):
        state.delay = 0.4
        uvicorn.run(
            create_app(
                Path(sys.argv[1]),
                dev_ui=True,
                ui_dir=Path(sys.argv[2]),
                ollama_client=OllamaClient.for_test_server(port),
            ),
            host="127.0.0.1",
            port=8765,
            proxy_headers=False,
            access_log=False,
        )
