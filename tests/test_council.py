import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from village.config import CouncilConfig
from village.council.engine import CouncilEngine
from village.council.personas import Persona, PersonaLoader
from village.council.resolution import (
    ResolutionStrategy,
    resolve_debate,
)
from village.council.transcript import (
    Transcript,
    TurnEntry,
    format_transcript,
    save_transcript,
)


class TestPersonaFromMarkdown:
    def test_parses_frontmatter_and_body(self) -> None:
        content = (
            "---\nname: skeptic\nmodel: anthropic/claude-3.5-sonnet"
            "\ntemperature: 0.7\ntags: [critical, analytical]"
            "\n---\n\nYou are a skeptical thinker."
        )
        persona = Persona.from_markdown(content)
        assert persona.name == "skeptic"
        assert persona.model == "anthropic/claude-3.5-sonnet"
        assert persona.temperature == 0.7
        assert persona.tags == ["critical", "analytical"]
        assert "skeptical thinker" in persona.system_prompt

    def test_defaults_when_missing_fields(self) -> None:
        content = "---\nname: minimal\n---\n\nSome prompt."
        persona = Persona.from_markdown(content)
        assert persona.name == "minimal"
        assert persona.model == "anthropic/claude-3.5-sonnet"
        assert persona.temperature == 0.7
        assert persona.tags == []

    def test_roundtrip_markdown(self) -> None:
        original = Persona(
            name="test",
            model="openrouter/auto",
            temperature=0.5,
            tags=["a", "b"],
            system_prompt="Be helpful.",
        )
        md = original.to_markdown()
        restored = Persona.from_markdown(md)
        assert restored.name == original.name
        assert restored.model == original.model
        assert restored.temperature == original.temperature
        assert restored.tags == original.tags
        assert restored.system_prompt == original.system_prompt


class TestPersonaLoaderLoad:
    def test_loads_existing_persona(self, tmp_path: Path) -> None:
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "skeptic.md").write_text(
            "---\nname: skeptic\ntags: [critical]\n---\n\nQuestion everything.",
            encoding="utf-8",
        )

        loader = PersonaLoader(personas_dir)
        persona = loader.load("skeptic")
        assert persona.name == "skeptic"
        assert "critical" in persona.tags

    def test_raises_for_missing_persona(self, tmp_path: Path) -> None:
        loader = PersonaLoader(tmp_path / "personas")
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load("nonexistent")


class TestPersonaLoaderLoadAll:
    def test_loads_all_personas(self, tmp_path: Path) -> None:
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "skeptic.md").write_text("---\nname: skeptic\n---\n\nBe skeptical.", encoding="utf-8")
        (personas_dir / "optimist.md").write_text("---\nname: optimist\n---\n\nBe positive.", encoding="utf-8")

        loader = PersonaLoader(personas_dir)
        all_p = loader.load_all()
        names = {p.name for p in all_p}
        assert names == {"skeptic", "optimist"}

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        loader = PersonaLoader(tmp_path / "nonexistent")
        assert loader.load_all() == []


class TestPersonaLoaderCreate:
    def test_creates_new_persona_file(self, tmp_path: Path) -> None:
        loader = PersonaLoader(tmp_path / "personas")
        persona = loader.create_persona("analyst", "You analyze data carefully.")
        assert persona.name == "analyst"
        assert "analyze data" in persona.system_prompt

        loaded = loader.load("analyst")
        assert loaded.name == "analyst"

    def test_returns_existing_if_file_exists(self, tmp_path: Path) -> None:
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "existing.md").write_text("---\nname: existing\n---\n\nOriginal prompt.", encoding="utf-8")

        loader = PersonaLoader(personas_dir)
        persona = loader.create_persona("existing", "New prompt.")
        assert "Original prompt" in persona.system_prompt

    def test_uses_default_description_when_empty(self, tmp_path: Path) -> None:
        loader = PersonaLoader(tmp_path / "personas")
        persona = loader.create_persona("helper", "")
        assert "helper" in persona.system_prompt


class TestResolveDebateSynthesis:
    def test_combines_all_responses(self) -> None:
        responses = {
            "alice": "We should use Python.",
            "bob": "Rust would be better.",
        }
        result = resolve_debate(ResolutionStrategy.SYNTHESIS, responses, "language choice")
        assert "alice" in result.summary
        assert "bob" in result.summary
        assert result.reasoning != ""
        assert result.winner is None


class TestResolveDebateVote:
    def test_produces_winner(self) -> None:
        responses = {
            "alice": "Option A",
            "bob": "Option B",
            "carol": "Option C",
        }
        result = resolve_debate(ResolutionStrategy.VOTE, responses, "best option")
        assert result.winner is not None
        assert result.winner in responses
        assert len(result.votes) == 3

    def test_votes_exclude_self(self) -> None:
        responses = {"alice": "A", "bob": "B"}
        result = resolve_debate(ResolutionStrategy.VOTE, responses, "pick")
        for voter, target in result.votes.items():
            assert voter != target


class TestResolveDebateArbiter:
    def test_uses_last_persona_as_default_arbiter(self) -> None:
        responses = {
            "alice": "First view",
            "bob": "Second view",
            "carol": "Final say",
        }
        result = resolve_debate(ResolutionStrategy.ARBITER, responses, "decision")
        assert result.winner == "carol"
        assert "Final say" in result.summary

    def test_uses_specified_arbiter(self) -> None:
        responses = {
            "alice": "My opinion",
            "bob": "Their opinion",
        }
        result = resolve_debate(ResolutionStrategy.ARBITER, responses, "topic", arbiter="alice")
        assert result.winner == "alice"


class TestResolveDebateInvalid:
    def test_raises_for_unknown_strategy(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            resolve_debate("invalid", {"a": "b"}, "t")  # type: ignore[arg-type]


class TestTranscriptFormat:
    def test_formats_markdown_transcript(self) -> None:
        now = datetime.now(timezone.utc)
        transcript = Transcript(
            council_id="council-abcd1234",
            meeting_type="debate",
            topic="What language to use",
            turns=[
                TurnEntry(persona_name="skeptic", content="Python has issues.", timestamp=now),
                TurnEntry(persona_name="pragmatist", content="Python is practical.", timestamp=now),
            ],
            created=now,
        )
        md = format_transcript(transcript)
        assert "council-abcd1234" in md
        assert "debate" in md
        assert "What language to use" in md
        assert "skeptic" in md
        assert "pragmatist" in md
        assert "Turn 1" in md
        assert "Turn 2" in md


class TestTranscriptSave:
    def test_saves_to_wiki_councils_dir(self, tmp_path: Path) -> None:
        transcript = Transcript(
            council_id="council-test123",
            meeting_type="chat",
            topic="Test topic",
            turns=[TurnEntry(persona_name="bot", content="Hello")],
        )
        path = save_transcript(transcript, tmp_path)
        assert path.exists()
        assert path.name == "transcript.md"
        assert "council-test123" in path.parent.name

        content = path.read_text(encoding="utf-8")
        assert "Test topic" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        transcript = Transcript(
            council_id="council-xyz789",
            meeting_type="debate",
            topic="New topic",
            turns=[],
        )
        path = save_transcript(transcript, tmp_path)
        assert path.exists()


class TestCouncilEngineStartMeeting:
    def test_starts_chat_meeting(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Test topic")
        assert state.council_id.startswith("council-")
        assert state.meeting_type == "chat"
        assert state.topic == "Test topic"
        assert state.status == "active"

    def test_starts_debate_with_rounds(self, tmp_path: Path) -> None:
        config = CouncilConfig(default_rounds=5)
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Debate topic", meeting_type="debate")
        assert state.meeting_type == "debate"
        assert state.max_rounds == 5

    def test_uses_specified_personas(self, tmp_path: Path) -> None:
        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()
        (personas_dir / "testy.md").write_text(
            "---\nname: testy\ntags: [test]\n---\n\nI test things.", encoding="utf-8"
        )

        config = CouncilConfig(personas_dir=str(personas_dir))
        engine = CouncilEngine(config=config, personas_dir=personas_dir)
        state = engine.start_meeting("Topic", persona_names=["testy"])
        assert len(state.personas) == 1
        assert state.personas[0].name == "testy"

    def test_auto_creates_missing_personas(self, tmp_path: Path) -> None:
        config = CouncilConfig(personas_dir=str(tmp_path / "personas"))
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic", persona_names=["newbie"])
        assert len(state.personas) == 1
        assert state.personas[0].name == "newbie"


class TestCouncilEngineRunRound:
    def test_records_turns_from_responses(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic")

        personas = {p.name for p in state.personas}
        responses = {name: f"Response from {name}" for name in personas}

        turns = engine.run_round(state, persona_responses=responses)
        assert len(turns) == len(personas)
        assert all(t.content.startswith("Response from") for t in turns)

    def test_increments_round_counter(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic", meeting_type="debate")

        engine.run_round(state)
        assert state.current_round == 1

        engine.run_round(state)
        assert state.current_round == 2

    def test_stops_at_max_rounds(self, tmp_path: Path) -> None:
        config = CouncilConfig(default_rounds=1)
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic", meeting_type="debate")

        engine.run_round(state)
        turns = engine.run_round(state)
        assert turns == []
        assert state.status == "ready_for_resolution"

    def test_rejects_inactive_meeting(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic")
        state.status = "resolved"

        turns = engine.run_round(state)
        assert turns == []


class TestCouncilEngineResolve:
    def test_resolves_meeting(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic")

        personas = {p.name for p in state.personas}
        responses = {name: f"View from {name}" for name in personas}
        engine.run_round(state, persona_responses=responses)

        result = engine.resolve(state)
        assert result.summary != ""
        assert state.status == "resolved"

    def test_resolution_stored_on_state(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Topic")

        personas = {p.name for p in state.personas}
        responses = {name: f"View from {name}" for name in personas}
        engine.run_round(state, persona_responses=responses)

        result = engine.resolve(state)
        assert state.resolution is result


class TestCouncilEngineLifecycle:
    def test_full_lifecycle_start_run_resolve(self, tmp_path: Path) -> None:
        config = CouncilConfig(default_rounds=2)
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas", wiki_dir=tmp_path / "wiki")

        state = engine.start_meeting("Full lifecycle test", meeting_type="debate")

        personas = {p.name for p in state.personas}
        responses = {name: f"Round response from {name}" for name in personas}

        engine.run_round(state, persona_responses=responses)
        engine.run_round(state, persona_responses=responses)

        engine.resolve(state)
        assert state.status == "resolved"

        transcript = engine.get_transcript(state)
        assert transcript.council_id == state.council_id
        assert len(transcript.turns) == len(personas) * 2

        path = engine.save_and_close(state)
        assert path is not None
        assert path.exists()


class TestCouncilEngineGetMeeting:
    def test_retrieves_existing_meeting(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        state = engine.start_meeting("Retrieve test")
        retrieved = engine.get_meeting(state.council_id)
        assert retrieved is state

    def test_returns_none_for_unknown(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        assert engine.get_meeting("council-nonexistent") is None


class TestCouncilEngineListMeetings:
    def test_lists_all_meetings(self, tmp_path: Path) -> None:
        config = CouncilConfig()
        engine = CouncilEngine(config=config, personas_dir=tmp_path / "personas")
        engine.start_meeting("Topic 1")
        engine.start_meeting("Topic 2")
        assert len(engine.list_meetings()) == 2


class TestCouncilConfigParsing:
    def test_defaults(self) -> None:
        config = CouncilConfig()
        assert config.default_type == "chat"
        assert config.max_turns == 10
        assert config.extension_turns == 5
        assert config.default_rounds == 3
        assert config.resolution_strategy == "synthesis"
        assert config.personas_dir == "personas/"

    def test_from_env_and_config_defaults(self) -> None:
        config = CouncilConfig.from_env_and_config({})
        assert config.default_type == "chat"
        assert config.max_turns == 10

    def test_from_env_and_config_with_values(self) -> None:
        file_config = {
            "council.default_type": "debate",
            "council.max_turns": "20",
            "council.default_rounds": "5",
            "council.resolution_strategy": "vote",
            "council.personas_dir": "my_personas/",
        }
        config = CouncilConfig.from_env_and_config(file_config)
        assert config.default_type == "debate"
        assert config.max_turns == 20
        assert config.default_rounds == 5
        assert config.resolution_strategy == "vote"
        assert config.personas_dir == "my_personas/"


class TestCouncilCLI:
    def test_council_help(self) -> None:
        from village.cli.council import council_group

        runner = CliRunner()
        result = runner.invoke(council_group, ["--help"])
        assert result.exit_code == 0
        assert "Multi-persona deliberation" in result.output

    def test_council_list_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(council_group, ["list"])
        assert result.exit_code == 0
        assert "No councils found" in result.output

    def test_council_list_json_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(council_group, ["list", "--json"])
        assert result.exit_code == 0
        assert result.output.strip() == "[]"

    def test_council_show_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(council_group, ["show", "council-nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_council_show_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)

        wiki_dir = tmp_path / "wiki" / "councils" / "council-testshow"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "transcript.md").write_text(
            "# Council Transcript: council-testshow\n\n"
            "- **Type**: chat\n- **Topic**: Show test\n\n---\n\n"
            "## Turn 1: bot\n\nHello\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(council_group, ["show", "council-testshow"])
        assert result.exit_code == 0
        assert "Show test" in result.output

    def test_council_show_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)

        wiki_dir = tmp_path / "wiki" / "councils" / "council-jsontest"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "transcript.md").write_text(
            "# Council Transcript: council-jsontest\n\n- **Type**: debate\n- **Topic**: JSON test\n\n---\n\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(council_group, ["show", "council-jsontest", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "metadata" in data

    def test_council_rematch_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(council_group, ["debate", "--from", "council-nonexistent", "--rematch"])
        assert result.exit_code == 1

    def test_council_rematch_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess

        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)

        wiki_dir = tmp_path / "wiki" / "councils" / "council-rematch1"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "transcript.md").write_text(
            "# Council Transcript: council-rematch1\n\n- **Type**: chat\n- **Topic**: Rematch test\n\n---\n\n",
            encoding="utf-8",
        )

        personas_dir = tmp_path / "personas"
        personas_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(council_group, ["debate", "--from", "council-rematch1", "--rematch"])
        assert result.exit_code == 0
        assert "Rematch:" in result.output

    def test_council_list_with_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)

        wiki_dir = tmp_path / "wiki" / "councils" / "council-listtest"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "transcript.md").write_text(
            "# Council Transcript: council-listtest\n\n- **Type**: debate\n- **Topic**: List test\n\n---\n\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(council_group, ["list"])
        assert result.exit_code == 0
        assert "council-listtest" in result.output

    def test_council_list_filter_by_type(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from village.cli.council import council_group

        monkeypatch.chdir(tmp_path)

        wiki_dir = tmp_path / "wiki" / "councils" / "council-filtertest"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "transcript.md").write_text(
            "# Council Transcript: council-filtertest\n\n- **Type**: chat\n- **Topic**: Filter test\n\n---\n\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(council_group, ["list", "--type", "debate"])
        assert result.exit_code == 0
        assert "council-filtertest" not in result.output
