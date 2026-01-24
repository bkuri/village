"""Test prompt generation (PPC + Fabric → Fabric → Embedded)."""

from unittest.mock import patch

from village.chat.prompts import detect_prompt_backend


def test_detect_backend_none_available():
    """Test backend detection when neither PPC nor Fabric available."""
    from village.chat.prompts import SubprocessError

    with patch("village.chat.prompts.run_command_output") as mock_run:
        mock_run.side_effect = SubprocessError("ppc not found")

        backend, warning = detect_prompt_backend()

        assert backend == "embedded"
        assert warning is not None


def test_detect_backend_fabric_only():
    """Test backend detection when only Fabric available."""
    from village.chat.prompts import SubprocessError

    with patch("village.chat.prompts.run_command_output") as mock_run:

        def side_effect(cmd):
            if "ppc" in cmd:
                raise SubprocessError("ppc not found")
            return "Fabric version"

        mock_run.side_effect = side_effect

        backend, warning = detect_prompt_backend()

        assert backend == "fabric"
        assert warning is None


def test_detect_backend_ppc_fabric():
    """Test backend detection when both PPC and Fabric available."""

    with patch("village.chat.prompts.run_command_output") as mock_run:
        mock_run.return_value = "PPC v0.2.0"

        backend, warning = detect_prompt_backend()

        assert backend == "ppc_fabric"
        assert warning is None
