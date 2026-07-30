from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _compose(filename: str = "compose.yml") -> dict:
    return yaml.safe_load(
        (PROJECT_ROOT / filename).read_text(encoding="utf-8"),
    )


def _ollama_service(filename: str) -> dict:
    return _compose(filename)["services"]["ollama"]


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


def test_api_uses_the_shared_obsidian_vault_for_recipes() -> None:
    api = _compose()["services"]["api"]

    assert "/srv/obsidian/ReceptenVault:/data/vault" in api["volumes"]
    assert api["environment"]["RECIPES_PATH"] == "/data/vault"
    assert api["environment"]["VAULT_PATH"] == "/data/vault"


def test_obsidian_sync_shares_the_vault_and_persists_its_config() -> None:
    sync = _compose()["services"]["obsidian-sync"]

    assert sync["build"]["context"] == "./obsidian-sync"
    assert sync["container_name"] == "obsidian-sync"
    assert sync["volumes"] == [
        "/srv/obsidian/ReceptenVault:/vault",
        "/srv/obsidian/headless-config:/root/.config/obsidian-headless",
    ]
    assert sync["restart"] == "unless-stopped"
    assert (PROJECT_ROOT / "obsidian-sync" / "Dockerfile").is_file()
