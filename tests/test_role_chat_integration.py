from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from village.roles import run_role_chat


class TestRunRoleChatWithMockLlm:
    def test_run_role_chat_echo_response(self):
        inputs = iter(["hello", "/exit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner")
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("What do you want to accomplish?" in o for o in output_calls)
                assert any("[planner] Received: hello" in o for o in output_calls)

    def test_run_role_chat_with_mock_llm_fn(self):
        def mock_llm(prompt: str) -> str:
            return "mocked answer"

        inputs = iter(["question", "/exit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner", llm_call_fn=mock_llm)
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("mocked answer" in o for o in output_calls)


class TestExitBreaksLoop:
    def test_exit_command_breaks_loop(self):
        inputs = iter(["/exit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo"):
                run_role_chat("planner")

    def test_quit_command_breaks_loop(self):
        inputs = iter(["/quit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo"):
                run_role_chat("planner")

    def test_empty_input_breaks_loop(self):
        inputs = iter([""])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo"):
                run_role_chat("planner")

    def test_abort_breaks_loop(self):
        with patch("village.roles.click.prompt", side_effect=click.exceptions.Abort()):
            with patch("village.roles.click.echo"):
                run_role_chat("planner")

    def test_eof_breaks_loop(self):
        with patch("village.roles.click.prompt", side_effect=EOFError()):
            with patch("village.roles.click.echo"):
                run_role_chat("planner")


class TestHelpShowsSkills:
    def test_help_lists_skills(self):
        inputs = iter(["/help", "/exit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner")
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                help_text = [o for o in output_calls if "Available:" in o]
                assert len(help_text) == 1
                assert "workflows" in help_text[0]
                assert "show" in help_text[0]
                assert "design" in help_text[0]
                assert "refine" in help_text[0]

    def test_help_shows_exit_and_help_commands(self):
        inputs = iter(["/help", "/exit"])
        with patch("village.roles.click.prompt", side_effect=inputs):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("builder")
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("/exit to quit" in o for o in output_calls)
                assert any("/help for commands" in o for o in output_calls)


class TestRoutingDetectionTriggersCrossRole:
    def test_route_triggers_nested_role_chat(self):
        def mock_llm(prompt: str) -> str:
            return "[ROUTE:builder] Let's build it"

        planner_inputs = iter(["build something"])
        builder_inputs = iter(["task info", "/exit"])

        call_count = {"count": 0}

        def prompt_side_effect(*args, **kwargs):
            if call_count["count"] == 0:
                call_count["count"] += 1
                return next(planner_inputs)
            elif call_count["count"] == 1:
                call_count["count"] += 1
                return next(builder_inputs)
            else:
                return "/exit"

        with patch("village.roles.click.prompt", side_effect=prompt_side_effect):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner", llm_call_fn=mock_llm)
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("Routing to builder" in o for o in output_calls)
                assert any("Which workflow shall I run?" in o for o in output_calls)


class TestAdviseWithConfirmation:
    def test_advise_yes_routes(self):
        def mock_llm(prompt: str) -> str:
            return "[ADVISE:council] Time to discuss"

        prompts = iter(["discuss this", "Y"])
        builder_fallback = iter(["/exit"])

        call_count = {"count": 0}

        def prompt_side_effect(*args, **kwargs):
            idx = call_count["count"]
            call_count["count"] += 1
            if idx == 0:
                return next(prompts)
            elif idx == 1:
                return next(prompts)
            else:
                return next(builder_fallback)

        with patch("village.roles.click.prompt", side_effect=prompt_side_effect):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner", llm_call_fn=mock_llm)
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("sounds like a job for the council" in o for o in output_calls)
                assert any("Routing to council" in o for o in output_calls)

    def test_advise_no_stays(self):
        def mock_llm(prompt: str) -> str:
            return "[ADVISE:council] Time to discuss"

        prompts = iter(["discuss this", "n", "/exit"])

        call_count = {"count": 0}

        def prompt_side_effect(*args, **kwargs):
            call_count["count"] += 1
            return next(prompts)

        with patch("village.roles.click.prompt", side_effect=prompt_side_effect):
            with patch("village.roles.click.echo") as mock_echo:
                run_role_chat("planner", llm_call_fn=mock_llm)
                output_calls = [str(c.args[0]) for c in mock_echo.call_args_list]
                assert any("sounds like a job for the council" in o for o in output_calls)
                assert any("village council" in o for o in output_calls)
                routing_calls = [o for o in output_calls if "Routing to council" in o]
                assert len(routing_calls) == 0


class TestPlannerShowFallback:
    def test_missing_name_prompts_selection(self):
        from village.cli.planner import planner_group

        runner = CliRunner()
        with patch("village.cli.planner._get_loader") as mock_loader_fn:
            mock_loader = MagicMock()
            mock_loader.list_workflows.return_value = ["deploy-app", "run-tests"]
            mock_wf = MagicMock()
            mock_wf.name = "deploy-app"
            mock_wf.description = "Deploy the app"
            mock_wf.version = "1.0"
            mock_wf.inputs = []
            mock_wf.steps = []
            mock_loader.load.return_value = mock_wf
            mock_loader_fn.return_value = mock_loader

            result = runner.invoke(planner_group, ["show"], input="1\n")
            assert result.exit_code == 0
            assert "deploy-app" in result.output

    def test_missing_name_no_workflows(self):
        from village.cli.planner import planner_group

        runner = CliRunner()
        with patch("village.cli.planner._get_loader") as mock_loader_fn:
            mock_loader = MagicMock()
            mock_loader.list_workflows.return_value = []
            mock_loader_fn.return_value = mock_loader

            result = runner.invoke(planner_group, ["show"])
            assert result.exit_code == 0
            assert "No workflows found" in result.output

    def test_missing_name_invalid_selection(self):
        from village.cli.planner import planner_group

        runner = CliRunner()
        with patch("village.cli.planner._get_loader") as mock_loader_fn:
            mock_loader = MagicMock()
            mock_loader.list_workflows.return_value = ["deploy-app"]
            mock_loader_fn.return_value = mock_loader

            result = runner.invoke(planner_group, ["show"], input="5\n")
            assert result.exit_code != 0


class TestPlannerDesignFallback:
    def test_missing_goal_prompts(self):
        from village.cli.planner import planner_group

        runner = CliRunner()
        with patch("village.cli.planner._get_loader") as mock_loader_fn:
            with patch("village.cli.planner.Planner") as mock_planner_cls:
                mock_loader = MagicMock()
                mock_loader.list_workflows.return_value = []
                mock_loader_fn.return_value = mock_loader
                mock_planner = MagicMock()
                mock_planner.design.return_value = "designed workflow"
                mock_planner_cls.return_value = mock_planner

                result = runner.invoke(planner_group, ["design"], input="my new goal\n")
                assert result.exit_code == 0
                assert "designed workflow" in result.output


class TestBuilderRunFallback:
    def test_missing_name_prompts_selection(self):
        from village.cli.builder import builder_group

        runner = CliRunner()
        with patch("village.cli.builder._get_loader") as mock_loader_fn:
            mock_loader = MagicMock()
            mock_loader.list_workflows.return_value = ["build-api", "build-web"]
            mock_wf = MagicMock()
            mock_wf.name = "build-api"
            mock_wf.steps = []
            mock_wf.resolve_steps.return_value = []
            mock_loader.load.return_value = mock_wf
            mock_loader_fn.return_value = mock_loader

            with patch("village.cli.builder.Builder") as mock_builder_cls:
                mock_builder = MagicMock()
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.step_results = []
                mock_builder.run_sync.return_value = mock_result
                mock_builder_cls.return_value = mock_builder

                result = runner.invoke(builder_group, ["run"], input="1\n")
                assert result.exit_code == 0

    def test_missing_name_no_workflows(self):
        from village.cli.builder import builder_group

        runner = CliRunner()
        with patch("village.cli.builder._get_loader") as mock_loader_fn:
            mock_loader = MagicMock()
            mock_loader.list_workflows.return_value = []
            mock_loader_fn.return_value = mock_loader

            result = runner.invoke(builder_group, ["run"])
            assert result.exit_code == 0
            assert "No workflows found" in result.output


class TestBuilderStatusFallback:
    def test_missing_run_id_shows_message(self):
        from village.cli.builder import builder_group

        runner = CliRunner()
        result = runner.invoke(builder_group, ["status"])
        assert result.exit_code == 0
        assert "No runs tracked yet" in result.output


class TestLedgerShowFallback:
    def test_missing_task_id_prompts_selection(self):
        from village.cli.ledger import ledger_group

        runner = CliRunner()
        with patch("village.cli.ledger.get_config") as mock_config_fn:
            mock_config = MagicMock()
            mock_config.traces_dir = "/tmp/test_traces"
            mock_config_fn.return_value = mock_config

            with patch("village.cli.ledger.TraceReader") as mock_reader_cls:
                mock_reader = MagicMock()
                mock_reader.list_traced_tasks.return_value = ["bd-001", "bd-002"]
                mock_event = MagicMock()
                mock_event.timestamp = "2026-01-01T00:00:00"
                mock_event.event_type.value = "task_checkout"
                mock_event.task_id = "bd-001"
                mock_event.agent = "planner"
                mock_event.data = {}
                mock_event.sequence = 1
                mock_reader.read.return_value = [mock_event]
                mock_reader_cls.return_value = mock_reader

                with patch("village.cli.ledger.format_trace", return_value="formatted"):
                    result = runner.invoke(ledger_group, ["show"], input="1\n")
                    assert result.exit_code == 0
                    assert "formatted" in result.output

    def test_missing_task_id_no_ledgers(self):
        from village.cli.ledger import ledger_group

        runner = CliRunner()
        with patch("village.cli.ledger.get_config") as mock_config_fn:
            mock_config = MagicMock()
            mock_config.traces_dir = "/tmp/test_traces"
            mock_config_fn.return_value = mock_config

            with patch("village.cli.ledger.TraceReader") as mock_reader_cls:
                mock_reader = MagicMock()
                mock_reader.list_traced_tasks.return_value = []
                mock_reader_cls.return_value = mock_reader

                result = runner.invoke(ledger_group, ["show"])
                assert result.exit_code == 0
                assert "No ledgers found" in result.output
