# Village fish shell completion

complete -c village -w help

complete -c village -n "__fish_seen_subcommand_from planner" -a "list show approve delete resume design"
complete -c village -n "__fish_seen_subcommand_from planner; and __fish_seen_subcommand_from show approve delete resume" -a "(find .village/plans -mindepth 1 -maxdepth 2 -type d ! -name drafts ! -name approved 2>/dev/null | xargs -I {} basename {})"