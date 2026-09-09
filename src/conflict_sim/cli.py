"""Hydra entry point for individual simulations and parameter sweeps."""

import json
from contextlib import ExitStack
from pathlib import Path

import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig

from .agent import Agent
from .config import parse_config, primary_config_directory
from .engine import run
from .llm import DemoBackend, LLMError, OpenAIBackend, create_openai_client
from .storage import load_seed, save_run


@hydra.main(version_base="1.3", config_path="conf", config_name="config")
def main(raw: DictConfig) -> None:
    try:
        runtime = HydraConfig.get().runtime
        cfg = parse_config(raw, primary_config_directory())
        output = Path(runtime.output_dir) / "corpus"
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        seed_path = Path(cfg.seed_file)
        thread = load_seed(seed_path)
        seed_data = json.loads(seed_path.read_text(encoding="utf-8"))
        missing = {u.speaker for u in thread.utterances} - {a.name for a in cfg.agents}
        if missing:
            raise ValueError(f"Seed speakers need configured personas: {sorted(missing)}")

        with ExitStack() as stack:
            if cfg.backend == "demo":
                llm = DemoBackend()
            else:
                client = stack.enter_context(create_openai_client(Path(runtime.cwd) / ".env"))
                llm = OpenAIBackend(client)
            agents = [
                Agent(
                    name=spec.name,
                    persona=spec.persona,
                    availability=spec.availability,
                    llm=llm,
                    model_decide=cfg.model_decide or "demo",
                    model_speak=cfg.model_speak or "demo",
                    temperature=cfg.temperature,
                    context_size=cfg.context_size,
                    language=cfg.language,
                )
                for spec in cfg.agents
            ]
            result = run(agents, thread, cfg)
        save_run(output, result, cfg, seed_data)
    except (OSError, ValueError, LLMError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        f"Saved {len(thread.utterances) - 2} generated comments over {result.ticks} ticks "
        f"({result.stop_reason}, backend={cfg.backend}) to {output.resolve()}"
    )
