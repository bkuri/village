#!/bin/bash
# Village shell completion
# Source this file or add to ~/.bashrc

_village_complete() {
    local cur prev prev2
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    prev2="${COMP_WORDS[COMP_CWORD-2]}"

    case "${prev}" in
        village)
            COMPREPLY=( $(compgen -W "planner builder watcher scribe greeter goals council doctor tasks" -- ${cur}) )
            ;;
        planner)
            if [[ "${prev2}" == "village" ]]; then
                COMPREPLY=( $(compgen -W "list show approve delete resume design workflows inspect" -- ${cur}) )
            fi
            ;;
        show|approve|delete|resume)
            # Get plan slugs from .village/plans/
            local plans_dir=".village/plans"
            if [ -d "$plans_dir" ]; then
                local slugs=$(find "$plans_dir" -mindepth 1 -maxdepth 2 -type d ! -name 'drafts' ! -name 'approved' 2>/dev/null | xargs -I {} basename {} | sort -u)
                COMPREPLY=( $(compgen -W "${slugs}" -- ${cur}) )
            fi
            ;;
    esac
}

complete -F _village_complete village