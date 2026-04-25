from pathlib import Path
from unittest.mock import patch

from village.hooks import MANAGED_HOOKS, install_hooks, uninstall_hooks


class TestManagedHooks:
    def test_all_hook_templates_exist(self) -> None:
        """Every hook in MANAGED_HOOKS has a corresponding .sh template."""
        from village.hooks import HOOKS_DIR

        for hook_name in MANAGED_HOOKS:
            source = HOOKS_DIR / f"{hook_name}.sh"
            assert source.exists(), f"Missing hook template: {source}"

    def test_all_templates_are_executable(self) -> None:
        from village.hooks import HOOKS_DIR

        for hook_name in MANAGED_HOOKS:
            source = HOOKS_DIR / f"{hook_name}.sh"
            assert source.stat().st_mode & 0o111 != 0, f"Hook template not executable: {source}"

    def test_all_templates_have_shebang(self) -> None:
        from village.hooks import HOOKS_DIR

        for hook_name in MANAGED_HOOKS:
            source = HOOKS_DIR / f"{hook_name}.sh"
            content = source.read_text(encoding="utf-8")
            assert content.startswith("#!/usr/bin/env bash"), f"Hook {hook_name} missing shebang"

    def test_all_templates_have_village_marker(self) -> None:
        from village.hooks import HOOKS_DIR

        for hook_name in MANAGED_HOOKS:
            source = HOOKS_DIR / f"{hook_name}.sh"
            content = source.read_text(encoding="utf-8")
            assert "Installed by: village" in content, f"Hook {hook_name} missing Village marker"


class TestInstallHooks:
    def test_fresh_install_all_hooks(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()

        # Create fake sources for all hooks
        sources = {}
        for hook_name in MANAGED_HOOKS:
            src = tmp_path / f"{hook_name}.sh"
            src.write_text(f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n", encoding="utf-8")
            sources[hook_name] = src

        with patch("village.hooks.HOOKS_DIR", tmp_path):
            result = install_hooks(git_root)
            assert result is True

        hooks_dir = git_root / ".git" / "hooks"
        for hook_name in MANAGED_HOOKS:
            hook = hooks_dir / hook_name
            assert hook.exists(), f"Hook not installed: {hook_name}"
            assert hook.stat().st_mode & 0o111 != 0

    def test_hooks_already_up_to_date(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        for hook_name in MANAGED_HOOKS:
            src = tmp_path / f"{hook_name}.sh"
            content = f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n"
            src.write_text(content, encoding="utf-8")
            (hooks_dir / hook_name).write_text(content, encoding="utf-8")

        with patch("village.hooks.HOOKS_DIR", tmp_path):
            result = install_hooks(git_root)
            assert result is True

    def test_outdated_village_hook_gets_replaced(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_name = "pre-commit"
        old_content = "#!/bin/bash\n# Installed by: village up\necho old\n"
        new_content = "#!/bin/bash\n# Installed by: village up\necho new\n"

        # Must provide sources for all managed hooks
        for name in MANAGED_HOOKS:
            src = tmp_path / f"{name}.sh"
            if name == hook_name:
                src.write_text(new_content, encoding="utf-8")
            else:
                src.write_text(f"#!/bin/bash\n# Installed by: village up\necho {name}\n", encoding="utf-8")

        (hooks_dir / hook_name).write_text(old_content, encoding="utf-8")

        with patch("village.hooks.HOOKS_DIR", tmp_path):
            result = install_hooks(git_root)
            assert result is True

        assert (hooks_dir / hook_name).read_text(encoding="utf-8").strip() == new_content.strip()

    def test_non_village_hook_not_overwritten(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        hook_name = "pre-commit"
        # User-created hook without Village marker
        user_content = "#!/bin/bash\necho my custom hook\n"
        (hooks_dir / hook_name).write_text(user_content, encoding="utf-8")

        src = tmp_path / f"{hook_name}.sh"
        src.write_text(f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n", encoding="utf-8")

        with patch("village.hooks.HOOKS_DIR", tmp_path):
            result = install_hooks(git_root)
            # Returns False because one hook was skipped
            assert result is False

        # Original content preserved
        assert (hooks_dir / hook_name).read_text(encoding="utf-8") == user_content

    def test_template_not_found(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git" / "hooks").mkdir(parents=True)

        # HOOKS_DIR points to empty dir — no templates
        empty_dir = tmp_path / "templates"
        empty_dir.mkdir()

        with patch("village.hooks.HOOKS_DIR", empty_dir):
            result = install_hooks(git_root)
            assert result is False

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()

        for hook_name in MANAGED_HOOKS:
            src = tmp_path / f"{hook_name}.sh"
            src.write_text(f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n", encoding="utf-8")

        with patch("village.hooks.HOOKS_DIR", tmp_path):
            result = install_hooks(git_root, dry_run=True)
            assert result is True

        hooks_dir = git_root / ".git" / "hooks"
        for hook_name in MANAGED_HOOKS:
            assert not (hooks_dir / hook_name).exists()


class TestUninstallHooks:
    def test_uninstall_all_village_hooks(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        for hook_name in MANAGED_HOOKS:
            (hooks_dir / hook_name).write_text(
                f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n", encoding="utf-8"
            )

        result = uninstall_hooks(git_root)
        assert result is True

        for hook_name in MANAGED_HOOKS:
            assert not (hooks_dir / hook_name).exists()

    def test_uninstall_skips_non_village_hooks(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        # User-created hook
        (hooks_dir / "pre-commit").write_text("#!/bin/bash\necho mine\n", encoding="utf-8")
        # Village hook
        (hooks_dir / "pre-tag").write_text("#!/bin/bash\n# Installed by: village up\necho tag\n", encoding="utf-8")

        result = uninstall_hooks(git_root)
        assert result is False  # False because one hook couldn't be removed

        assert (hooks_dir / "pre-commit").exists()  # User hook preserved
        assert not (hooks_dir / "pre-tag").exists()  # Village hook removed

    def test_hooks_not_installed(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git" / "hooks").mkdir(parents=True)

        result = uninstall_hooks(git_root)
        assert result is True

    def test_no_git_dir(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()

        result = uninstall_hooks(git_root)
        assert result is True

    def test_dry_run_does_not_remove(self, tmp_path: Path) -> None:
        git_root = tmp_path / "repo"
        git_root.mkdir()
        hooks_dir = git_root / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        for hook_name in MANAGED_HOOKS:
            (hooks_dir / hook_name).write_text(
                f"#!/bin/bash\n# Installed by: village up\necho {hook_name}\n", encoding="utf-8"
            )

        result = uninstall_hooks(git_root, dry_run=True)
        assert result is True

        for hook_name in MANAGED_HOOKS:
            assert (hooks_dir / hook_name).exists()


class TestIsVillageHook:
    def test_village_hook_detected(self, tmp_path: Path) -> None:
        from village.hooks import _is_village_hook

        hook = tmp_path / "pre-commit"
        hook.write_text("#!/bin/bash\n# Installed by: village up\necho hi\n", encoding="utf-8")
        assert _is_village_hook(hook) is True

    def test_non_village_hook_not_detected(self, tmp_path: Path) -> None:
        from village.hooks import _is_village_hook

        hook = tmp_path / "pre-commit"
        hook.write_text("#!/bin/bash\necho my custom hook\n", encoding="utf-8")
        assert _is_village_hook(hook) is False

    def test_nonexistent_hook(self, tmp_path: Path) -> None:
        from village.hooks import _is_village_hook

        assert _is_village_hook(tmp_path / "nonexistent") is False
