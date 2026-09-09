"""Hydra composes settings; Pydantic validates the resolved simulation inputs."""

from importlib.resources import files
from pathlib import Path
from typing import Literal, Self

from hydra import compose, initialize_config_dir
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from pydantic import Field, model_validator

from .models import NonEmptyText, Probability, ValidatedModel


class RunConfig(ValidatedModel):
    rule: Literal["round_robin", "random", "bidding", "event_driven"] = "bidding"
    max_ticks: int = Field(default=12, ge=1)
    silence_limit: int = Field(default=2, ge=1)
    random_seed: int = 7


class AgentSpec(ValidatedModel):
    name: NonEmptyText
    persona: NonEmptyText
    availability: Probability = 0.7


class Config(RunConfig):
    n_agents: int = Field(default=4, ge=3, le=6)
    seed_file: NonEmptyText = "seeds/example.json"
    agents: list[AgentSpec]
    backend: Literal["demo", "openai"] = "demo"
    model_decide: NonEmptyText | None = None
    model_speak: NonEmptyText | None = None
    temperature: float = Field(default=0.8, ge=0, le=2)
    context_size: int = Field(default=10, ge=1)
    language: NonEmptyText = "English"

    @model_validator(mode="after")
    def check_relationships(self) -> Self:
        if self.n_agents != len(self.agents):
            raise ValueError("n_agents must match the number of configured agents")
        if len({agent.name.casefold() for agent in self.agents}) != self.n_agents:
            raise ValueError("Agent names must be unique (case insensitive)")
        if self.backend == "openai" and (self.model_decide is None or self.model_speak is None):
            raise ValueError("Set model_decide and model_speak before using the openai backend")
        return self


def parse_config(raw: DictConfig, directory: Path) -> Config:
    cfg = Config.model_validate(OmegaConf.to_container(raw, resolve=True, throw_on_missing=True))
    return cfg.model_copy(update={"seed_file": str((directory / cfg.seed_file).resolve())})


def primary_config_directory() -> Path:
    """Find the selected primary YAML in Hydra's file/package search order."""
    hydra_cfg = HydraConfig.get()
    name = hydra_cfg.job.config_name
    filename = name if name.endswith(".yaml") else f"{name}.yaml"
    for source in hydra_cfg.runtime.config_sources:
        if source.schema not in ("file", "pkg"):
            continue
        directory = Path(str(files(source.path))) if source.schema == "pkg" else Path(source.path)
        candidate = directory / filename
        if candidate.is_file():
            return candidate.parent
    raise ValueError(f"Cannot locate primary config: {filename}")


def load_config(path: Path, overrides: list[str] | None = None) -> Config:
    """Compose a config outside the CLI, without changing Hydra's global state."""
    path = path.resolve()
    with initialize_config_dir(version_base="1.3", config_dir=str(path.parent)):
        raw = compose(config_name=path.stem, overrides=overrides or [])
        return parse_config(raw, path.parent)
