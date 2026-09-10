"""Hydra entry point for individual simulations and parameter sweeps."""

from pathlib import Path

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from .agent import Agent
from .engine import run
from .llm import DemoBackend, LLMError, OpenAIBackend, create_openai_client
from .models import Config
from .storage import load_seed, save_run

CONF_DIR = Path(__file__).resolve().parents[2] / "conf"


def parse_config(raw: DictConfig) -> Config:
    return Config.model_validate(OmegaConf.to_container(raw, resolve=True, throw_on_missing=True))


@hydra.main(version_base="1.3", config_path=str(CONF_DIR), config_name="config")
def main(raw: DictConfig) -> None:
    try:
        runtime = HydraConfig.get().runtime
        cfg = parse_config(raw)
        output = Path(runtime.output_dir) / "corpus"
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        # Relative seed paths follow the launch directory, even when Hydra chdirs.
        seed_path = (
            CONF_DIR / "seeds/example.json"
            if cfg.seed_file is None
            else Path(runtime.cwd) / cfg.seed_file
        )
        thread, seed_data = load_seed(seed_path)
        missing = {u.speaker for u in thread.utterances} - {a.name for a in cfg.agents}
        if missing:
            raise ValueError(f"Seed speakers need configured personas: {sorted(missing)}")

        if cfg.backend == "demo":
            llm = DemoBackend()
        else:
            llm = OpenAIBackend(
                create_openai_client(Path(runtime.cwd) / ".env"),
                reasoning_effort=cfg.reasoning_effort,
            )
        agents = [
            Agent(
                name=spec.name,
                persona=spec.persona,
                availability=spec.availability,
                llm=llm,
                # The demo backend ignores the model ID; the openai backend requires one.
                model_decide=cfg.model_decide or "demo",
                model_speak=cfg.model_speak or "demo",
                temperature=cfg.temperature,
                context_size=cfg.context_size,
                memory_mode=cfg.memory_mode,
                language=cfg.language,
            )
            for spec in cfg.agents
        ]
        result = run(
            agents,
            thread,
            rule=cfg.rule,
            max_ticks=cfg.max_ticks,
            silence_limit=cfg.silence_limit,
            random_seed=cfg.random_seed,
        )
        save_run(output, result, cfg, seed_data)
    except (OSError, ValueError, LLMError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        f"Saved {len(thread.utterances) - 2} generated comments over {result.ticks} ticks "
        f"({result.stop_reason}, backend={cfg.backend}) to {output.resolve()}"
    )
