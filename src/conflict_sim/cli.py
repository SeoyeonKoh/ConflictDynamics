"""Hydra entry point for individual simulations and parameter sweeps."""

import random
import sys
from pathlib import Path
from time import sleep

import hydra
from hydra.core.hydra_config import HydraConfig
from hydra.experimental.callback import Callback
from omegaconf import DictConfig, OmegaConf

from .agent import Agent
from .conversation import RunResult, run
from .environment import Environment
from .llm import DemoBackend, LanguageModel, LLMError, OpenAIBackend, create_openai_client
from .loop import Loop
from .models import Config
from .storage import RunWriter, load_seed, save_company_run, save_run, write_json

CONF_DIR = Path(__file__).resolve().parents[2] / "conf"


class ProtectOutput(Callback):
    """Reserve the destination before Hydra opens logs or writes its configuration."""

    def reserve(self, directory: str) -> None:
        path = Path(directory)
        try:
            path.mkdir(parents=True, exist_ok=True)
            # The live UI opens console.log before starting the child process.
            if any(child.name != "console.log" for child in path.iterdir()):
                raise FileExistsError(f"Output already contains a run: {path}")
            (path / ".run.lock").touch(exist_ok=False)
        except OSError as exc:
            # Hydra warns and continues for Exception in callbacks; this must stop the job.
            raise SystemExit(f"error: {exc}") from exc

    def on_run_start(self, config: DictConfig, **kwargs) -> None:
        self.reserve(config.hydra.run.dir)

    def on_multirun_start(self, config: DictConfig, **kwargs) -> None:
        subdir = OmegaConf.to_container(config.hydra.sweep, resolve=False)["subdir"]
        if subdir != "${hydra.job.num}":
            raise SystemExit("error: use hydra.sweep.subdir=${hydra.job.num} for unique job paths")
        self.reserve(config.hydra.sweep.dir)


def parse_config(raw: DictConfig) -> Config:
    return Config.model_validate(OmegaConf.to_container(raw, resolve=True, throw_on_missing=True))


@hydra.main(version_base="1.3", config_path=str(CONF_DIR), config_name="config")
def simulate(raw: DictConfig) -> None:
    runtime = HydraConfig.get().runtime
    live_path = Path(runtime.output_dir) / "live.json"
    progress = {"ticks": 0, "utterances": [], "decisions": []}
    llm = None

    def publish(result: RunResult | None, message: str, status: str = "running") -> None:
        if raw.get("live") is not True:
            return
        if result is not None:
            utterances = []
            for utterance in result.thread.utterances:
                row = utterance.model_dump()
                row["reply-to"] = row.pop("reply_to")
                utterances.append(row)
            progress.update(ticks=result.ticks, utterances=utterances, decisions=result.decisions)
        progress.update(status=status, message=message)
        if isinstance(llm, OpenAIBackend):
            progress["llm_usage"] = llm.usage
        temporary = live_path.with_suffix(".tmp")
        write_json(temporary, progress)
        temporary.replace(live_path)  # Readers see a complete snapshot, even during an API call.
        if raw.get("backend") == "demo" and status == "running":
            sleep(0.2)

    try:
        cfg = parse_config(raw)
        progress["config"] = cfg.model_dump()
        output = Path(runtime.output_dir) / "corpus"
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        llm = _backend(cfg, Path(runtime.cwd))
        usage = llm.usage if isinstance(llm, OpenAIBackend) else None
        if cfg.environment is not None:
            summary = _company_run(cfg, llm, Path(runtime.output_dir), output, usage)
        else:
            summary = _wiki_run(cfg, llm, Path(runtime.cwd), output, usage, publish)
    except (OSError, ValueError, LLMError) as exc:
        publish(None, str(exc), "failed")
        raise SystemExit(f"error: {exc}") from exc
    finally:
        if isinstance(llm, OpenAIBackend):
            write_json(Path(runtime.output_dir) / "usage.json", llm.usage)
    print(f"{summary} (backend={cfg.backend}) to {output.resolve()}")


def _backend(cfg: Config, cwd: Path) -> LanguageModel:
    if cfg.backend == "demo":
        return DemoBackend(
            blocked_nudge_ticks=cfg.blocked_nudge_ticks,
            blocked_report_ticks=cfg.blocked_report_ticks,
        )
    return OpenAIBackend(
        create_openai_client(cwd / ".env"),
        model_embed=cfg.model_embed,
        reasoning_effort=cfg.reasoning_effort,
        max_tokens_decide=cfg.max_tokens_decide,
        max_tokens_speak=cfg.max_tokens_speak,
        max_total_tokens=cfg.max_total_tokens,
        max_input_chars=cfg.max_input_chars,
    )


def _wiki_run(cfg: Config, llm, cwd: Path, output: Path, usage, publish) -> str:
    """The wiki preset: one session stepped from a seed thread."""
    # Relative seed paths follow the launch directory, even when Hydra chdirs.
    seed_path = CONF_DIR / "seeds/example.json" if cfg.seed_file is None else cwd / cfg.seed_file
    thread, seed_data = load_seed(seed_path)
    missing = {u.speaker for u in thread.utterances} - {a.name for a in cfg.agents}
    if missing:
        raise ValueError(f"Seed speakers need configured personas: {sorted(missing)}")
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    result = run(
        agents,
        thread,
        rule=cfg.rule,
        max_ticks=cfg.max_ticks,
        max_utterances=cfg.max_utterances,
        silence_limit=cfg.silence_limit,
        random_seed=cfg.random_seed,
        on_update=publish if cfg.live else None,
    )
    save_run(output, result, cfg, seed_data, usage)
    publish(result, f"Completed · {result.stop_reason}", "completed")
    generated = len(thread.utterances) - result.seed_count
    return f"Saved {generated} generated comments over {result.ticks} ticks ({result.stop_reason})"


def _company_run(cfg: Config, llm, run_dir: Path, output: Path, usage) -> str:
    """The company world: `max_days` days of the tick loop, files written as it goes."""
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    env = Environment(cfg.environment, cfg.agents)
    writer = RunWriter(run_dir)
    try:
        loop = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer=writer)
        result = loop.run()
    finally:
        writer.close()
    save_company_run(
        output, cfg, loop.threads, loop.sessions, ticks=result.ticks, days=result.days, usage=usage
    )
    posts = sum(len(thread.utterances) for thread in loop.threads.values())
    return (
        f"Saved {posts} utterances in {len(loop.threads)} sessions over {result.ticks} ticks "
        f"({result.stop_reason})"
    )


def main() -> None:
    # Enforce protection even when the caller supplies a different config directory.
    sys.argv.append("++hydra.callbacks.protect_output._target_=conflict_sim.cli.ProtectOutput")
    try:
        simulate()
    finally:
        sys.argv.pop()


if __name__ == "__main__":
    main()
