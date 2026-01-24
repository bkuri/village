# Shell Completion for Village

Village provides shell completion for bash and zsh via Click 8.1+'s built-in completion system.

## Bash Completion

### Setup

Add the following to your `~/.bashrc`:

```bash
# Bash completion for village
eval "$(_VILLAGE_COMPLETE=bash_source village)"
```

Then reload your shell:

```bash
source ~/.bashrc
```

### Usage

```bash
village <TAB>              # Complete commands
village status <TAB>         # Complete status options
village resume <TAB>         # Complete task IDs (if beads available)
village queue <TAB>         # Complete queue options
```

## Zsh Completion

### Setup

Add the following to your `~/.zshrc`:

```zsh
# Zsh completion for village
eval "$(_VILLAGE_COMPLETE=zsh_source village)"
```

Then reload your shell:

```zsh
source ~/.zshrc
```

### Usage

```zsh
village <TAB>              # Complete commands
village status <TAB>         # Complete status options
village resume <TAB>         # Complete task IDs (if beads available)
village queue <TAB>         # Complete queue options
```

## Fish Completion (Future Enhancement)

Fish completion is supported by Click but requires manual setup.

To enable when available:

```fish
# Add to ~/.config/fish/completions/village.fish
eval "$(_VILLAGE_COMPLETE=fish_source village)"
```

## Completion Sources

Village completion uses multiple sources:

1. **Commands**: `up`, `down`, `status`, `resume`, `queue`, `ready`, `cleanup`, `unlock`, `locks`
2. **Options**: `--verbose`, `--json`, `--workers`, `--orphans`, `--agent`, `--detached`, `--html`, `--dry-run`, `--apply`, `--force`, `--n`, `--short`, `--locks`
3. **Task IDs**: Retrieved from `bd ready` (if beads available)
4. **Agent Names**: Retrieved from `.village/config` agent definitions

## Troubleshooting

### Completion Not Working

**Symptom**: Tab completion doesn't work after setup.

**Solution 1**: Restart your shell
```bash
# Bash
exec bash

# Zsh
exec zsh
```

**Solution 2**: Check village is installed
```bash
which village
```

**Solution 3**: Verify completion variable is set
```bash
# Bash
echo $_VILLAGE_COMPLETE

# Zsh
echo $_VILLAGE_COMPLETE
```

Both should be `bash_source` or `zsh_source`.

### Task ID Completion Not Available

**Symptom**: `village resume <TAB>` doesn't complete task IDs.

**Solution**: Task ID completion requires Beads (`bd` command) to be available and initialized.

```bash
# Check if beads is available
bd --version

# Check if beads is initialized
ls .beads/
```

If beads is not available, use explicit task IDs instead of completion.

## Customizing Completion

Click's completion system supports dynamic completion via functions. Village can be extended to provide:

- Custom task ID sources (not just Beads)
- Agent name completion from `.village/config`
- Completion for custom contract files

This requires extending the Click command decorators with `shell_complete` parameters.
