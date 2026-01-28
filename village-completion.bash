# Village bash completion script

_village_completion() {
    local cur prev words cword
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cword="${COMP_WORDS[COMP_CWORD]}"

    case ${COMP_WORDS[0]} in
        village)
            case ${cword} in
                ""|*[!-]*)
                    COMPREPLY=($(compgen -W "${COMP_WORDS[@]}" -f -- ${cword}))
                    ;;
                -*)
                    COMPREPLY=($(compgen -W "${COMP_WORDS[@]}" -f -- ${cword}))
                    ;;
                *)
                    local commands="queue dequeue resume-task cancel-task status dashboard chat cleanup drafts help"
                    COMPREPLY=($(compgen -W "${commands}" -f -- ${cword}))
                    ;;
            esac
            ;;
    esac
}

complete -F _village_completion village
