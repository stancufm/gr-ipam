# Bash completion for gr-ipam.
# Set GR_COMPLETION_CISCO_STYLE=1 before this file is sourced to display
# ambiguous candidates on the first Tab instead of the standard second Tab.

if [[ ${GR_COMPLETION_CISCO_STYLE:-0} == 1 ]]; then
    bind 'set show-all-if-ambiguous on' 2>/dev/null || true
fi

_gr_complete_words() {
    local values=$1 current=$2
    COMPREPLY=( $(compgen -W "$values" -- "$current") )
}

_gr_complete_dynamic() {
    local action=$1 current=$2 value=${3-}
    local candidates
    if [[ -n $value ]]; then
        candidates=$(gr completion "$action" "$value" 2>/dev/null) || return
    else
        candidates=$(gr completion "$action" 2>/dev/null) || return
    fi
    COMPREPLY=( $(compgen -W "$candidates" -- "$current") )
}

_gr_completion() {
    local current previous command subcommand
    current=${COMP_WORDS[COMP_CWORD]}
    previous=${COMP_WORDS[COMP_CWORD-1]}
    command=${COMP_WORDS[1]-}
    subcommand=${COMP_WORDS[2]-}
    COMPREPLY=()

    if (( COMP_CWORD == 1 )); then
        _gr_complete_words "init doctor config ssh collect find search subnet local sync export auth vault update self-update migrate-ssh migrate-drivers vendor audit completion docs help --ssh --config --version" "$current"
        return
    fi

    case "$previous" in
        --config|--output|-o)
            COMPREPLY=( $(compgen -f -- "$current") )
            compopt -o filenames 2>/dev/null || true
            return
            ;;
        --profile)
            _gr_complete_dynamic profiles "$current"
            return
            ;;
        --driver|--device-driver)
            _gr_complete_dynamic drivers "$current"
            return
            ;;
        --client|--ssh-client)
            _gr_complete_words "normal legacy" "$current"
            return
            ;;
        --ssh-enabled)
            _gr_complete_words "yes no" "$current"
            return
            ;;
        --target)
            _gr_complete_words "all hosts ssh" "$current"
            return
            ;;
        --language)
            _gr_complete_words "en ro" "$current"
            return
            ;;
        --stream)
            _gr_complete_words "stdin stdout stderr" "$current"
            return
            ;;
    esac

    case "$command" in
        audit)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "show" "$current"
            elif [[ $subcommand == show && $COMP_CWORD -eq 3 ]]; then
                if [[ $current == -* ]]; then
                    _gr_complete_words "--include-stdin --stream --no-more --config --help" "$current"
                elif [[ $current == */* || $current == .* ]]; then
                    COMPREPLY=( $(compgen -f -- "$current") )
                    compopt -o filenames 2>/dev/null || true
                else
                    _gr_complete_dynamic audit-targets "$current"
                fi
            elif [[ $subcommand == show && $COMP_CWORD -eq 4 ]]; then
                if [[ $current == -* ]]; then
                    _gr_complete_words "--include-stdin --stream --no-more --config --help" "$current"
                else
                    _gr_complete_dynamic audit-sessions "$current" "${COMP_WORDS[3]}"
                fi
            elif [[ $subcommand == show && $current == -* ]]; then
                _gr_complete_words "--include-stdin --stream --no-more --config --help" "$current"
            fi
            ;;
        completion)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "bash profiles drivers audit-targets audit-sessions collect-reports" "$current"
            elif [[ $subcommand == audit-sessions && $COMP_CWORD -eq 3 ]]; then
                _gr_complete_dynamic audit-targets "$current"
            fi
            ;;
        doctor)
            _gr_complete_words "--api --system --config --help" "$current"
            ;;
        config)
            (( COMP_CWORD == 2 )) && _gr_complete_words "show --config --help" "$current"
            ;;
        init)
            _gr_complete_words "--configure-auth --config --help" "$current"
            ;;
        find|search|--ssh)
            if [[ $current == -* ]]; then
                _gr_complete_words "--brief --details --ssh --user --port --profile --client --driver --no-vault --audit --no-audit --config --help" "$current"
            fi
            ;;
        ssh)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "validate" "$current"
            elif [[ $subcommand == validate ]]; then
                _gr_complete_words "--run --workers --ip --config --help" "$current"
            fi
            ;;
        collect)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "version reports" "$current"
            elif [[ $subcommand == version ]]; then
                _gr_complete_words "--all --ip --vendor --workers --config --help" "$current"
            elif [[ $subcommand == reports && $COMP_CWORD -eq 3 ]]; then
                if [[ $current == -* ]]; then
                    _gr_complete_words "--raw --no-more --config --help" "$current"
                else
                    _gr_complete_dynamic collect-reports "$current"
                fi
            elif [[ $subcommand == reports && $current == -* ]]; then
                _gr_complete_words "--raw --no-more --config --help" "$current"
            fi
            ;;
        subnet|local)
            [[ $current == -* ]] && _gr_complete_words "--config --help" "$current"
            ;;
        sync)
            _gr_complete_words "--apply --target --config --help" "$current"
            ;;
        export)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "hosts ssh" "$current"
            else
                _gr_complete_words "--output -o --config --help" "$current"
            fi
            ;;
        auth)
            (( COMP_CWORD == 2 )) && _gr_complete_words "configure test" "$current"
            ;;
        vault)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "init list set test" "$current"
            elif [[ $subcommand == set || $subcommand == test ]]; then
                _gr_complete_dynamic profiles "$current"
            fi
            ;;
        update)
            _gr_complete_words "--apply --hostname --clear-hostname --ssh-enabled --ssh-user --clear-ssh-user --ssh-port --clear-ssh-port --ssh-profile --clear-ssh-profile --ssh-jump --clear-ssh-jump --ssh-client --clear-ssh-client --device-driver --clear-device-driver --device-vendor --clear-device-vendor --config --help" "$current"
            ;;
        self-update)
            _gr_complete_words "check --version --dry-run --yes --help" "$current"
            ;;
        migrate-ssh)
            _gr_complete_words "--apply --limit --config --help" "$current"
            ;;
        migrate-drivers)
            _gr_complete_words "--apply --limit --overwrite --config --help" "$current"
            ;;
        vendor)
            if (( COMP_CWORD == 2 )); then
                _gr_complete_words "update-db lookup sync" "$current"
            elif [[ $subcommand == sync ]]; then
                _gr_complete_words "--apply --overwrite --config --help" "$current"
            fi
            ;;
        docs|help)
            _gr_complete_words "--language --help" "$current"
            ;;
    esac
}

complete -F _gr_completion gr
