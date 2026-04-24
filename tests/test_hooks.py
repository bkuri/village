from pathlib import Path
from unittest.mock import patch


class TestInstallHooks:
    def test_template_not_found(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git" / "hooks").mkdir(parents=True)

        with patch("village.hooks.HOOK_SOURCE", tmp_path / "nonexistent.sh"):
            result = install_hooks(git_root)
            assert result is False

    def test_hook_already_up_to_date(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        source = tmp_path / "prepare-commit-msg.sh"
        source.write_text("#!/bin/bash\necho hello\n", encoding="utf-8")

        hook_target = hooks_dir / "prepare-commit-msg"
        hook_target.write_text("#!/bin/bash\necho hello\n", encoding="utf-8")

        with patch("village.hooks.HOOK_SOURCE", source):
            result = install_hooks(git_root)
            assert result is True

    def test_hook_outdated_installs_new(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        source = tmp_path / "prepare-commit-msg.sh"
        source.write_text("#!/bin/bash\necho new version\n", encoding="utf-8")

        hook_target = hooks_dir / "prepare-commit-msg"
        hook_target.write_text("#!/bin/bash\necho old version\n", encoding="utf-8")

        with patch("village.hooks.HOOK_SOURCE", source):
            result = install_hooks(git_root)
            assert result is True
            assert hook_target.read_text(encoding="utf-8").strip() == "#!/bin/bash\necho new version"
            assert hook_target.stat().st_mode & 0o111 != 0

    def test_fresh_install(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()

        source = tmp_path / "prepare-commit-msg.sh"
        source.write_text("#!/bin/bash\necho hook\n", encoding="utf-8")

        with patch("village.hooks.HOOK_SOURCE", source):
            result = install_hooks(git_root)
            assert result is True

        hook_target = git_root / ".git" / "hooks" / "prepare-commit-msg"
        assert hook_target.exists()
        assert hook_target.read_text(encoding="utf-8").strip() == "#!/bin/bash\necho hook"
        assert hook_target.stat().st_mode & 0o111 != 0

    def test_dry_run_does_not_write(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()

        source = tmp_path / "prepare-commit-msg.sh"
        source.write_text("#!/bin/bash\necho hook\n", encoding="utf-8")

        with patch("village.hooks.HOOK_SOURCE", source):
            result = install_hooks(git_root, dry_run=True)
            assert result is True

        hook_target = git_root / ".git" / "hooks" / "prepare-commit-msg"
        assert not hook_target.exists()

    def test_dry_run_with_existing_hook(self, tmp_path: Path):
        from village.hooks import install_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        source = tmp_path / "prepare-commit-msg.sh"
        source.write_text("#!/bin/bash\necho new\n", encoding="utf-8")

        hook_target = hooks_dir / "prepare-commit-msg"
        hook_target.write_text("#!/bin/bash\necho old\n", encoding="utf-8")

        with patch("village.hooks.HOOK_SOURCE", source):
            result = install_hooks(git_root, dry_run=True)
            assert result is True

        assert hook_target.read_text(encoding="utf-8").strip() == "#!/bin/bash\necho old"


class TestUninstallHooks:
    def test_hook_not_installed(self, tmp_path: Path):
        from village.hooks import uninstall_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git" / "hooks").mkdir(parents=True)

        result = uninstall_hooks(git_root)
        assert result is True

    def test_uninstall_existing_hook(self, tmp_path: Path):
        from village.hooks import uninstall_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_target = hooks_dir / "prepare-commit-msg"
        hook_target.write_text("#!/bin/bash\necho hook\n", encoding="utf-8")

        result = uninstall_hooks(git_root)
        assert result is True
        assert not hook_target.exists()

    def test_dry_run_does_not_remove(self, tmp_path: Path):
        from village.hooks import uninstall_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_target = hooks_dir / "prepare-commit-msg"
        hook_target.write_text("#!/bin/bash\necho hook\n", encoding="utf-8")

        result = uninstall_hooks(git_root, dry_run=True)
        assert result is True
        assert hook_target.exists()

    def test_no_git_dir(self, tmp_path: Path):
        from village.hooks import uninstall_hooks

        git_root = tmp_path / "repo"
        git_root.mkdir()

        result = uninstall_hooks(git_root)
        assert result is True
