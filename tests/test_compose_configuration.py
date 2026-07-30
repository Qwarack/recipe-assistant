from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ollama_service(filename: str) -> dict:
    compose = yaml.safe_load(
        (PROJECT_ROOT / filename).read_text(encoding="utf-8"),
    )
    return compose["services"]["ollama"]


def test_default_ollama_service_is_cpu_safe_and_resource_limited() -> None:
    ollama = _ollama_service("compose.yml")

    assert "gpus" not in ollama
    assert ollama["cpus"] == 3.0
    assert ollama["cpu_shares"] == 256
    assert ollama["mem_limit"] == "7g"
    assert ollama["mem_reservation"] == "4g"
    assert ollama["memswap_limit"] == "9g"


def test_gpu_override_explicitly_exposes_all_gpus() -> None:
    ollama = _ollama_service("compose.gpu.yml")

    assert ollama == {"gpus": "all"}
