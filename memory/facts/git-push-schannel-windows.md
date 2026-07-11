# git push over HTTPS on Windows: schannel "missing close_notify"

TL;DR: when `git push` over HTTPS on this Windows machine throws

```
fatal: unable to access 'https://github.com/<owner>/<repo>.git/':
       schannel: server closed abruptly (missing close_notify)
```

it is **not** an auth failure. It is Windows' native TLS stack (`schannel`) bailing on a clean TLS shutdown that the server does. The fix is to swap to OpenSSL's TLS backend for that single command, without touching any persistent git config:

```bash
git -c http.sslBackend=openssl -c http.version=HTTP/1.1 push -u origin main
```

Confirmed working on 2026-07-11 against `https://github.com/zhenyu666-debug/-666.git`:

- before: `fatal ... schannel: server closed abruptly (missing close_notify)`, exit 128
- after  : `branch 'main' set up to track 'origin/main'. main -> main`, exit 0
- local HEAD == remote HEAD == `ce0e2525...` (verified)

## Why

`schannel` (Windows native TLS) insists on a specific TLS shutdown handshake (the `close_notify` alert before the TCP FIN). GitHub's HTTPS endpoint occasionally terminates the connection without that alert under HTTP/2. Git's build on this machine links against `schannel` by default, so Git just propagates the failure as "server closed abruptly" plus the cryptic `missing close_notify`.

`http.sslBackend=openssl` tells Git to use the libssl that ships with this Git for Windows install, which handles the missing `close_notify` gracefully. Pairing with `http.version=HTTP/1.1` removes HTTP/2 from the picture entirely, which makes the workaround robust against future GitHub HTTP/2 tweaks.

## Hard rules while applying the fix

- Pass both `-c` flags inline. Do **not** run `git config --global` or `git config --local` to set them; the workspace's `AGENTS.md` forbids mutating git config.
- Do **not** touch `user.name` / `user.email` either. The commit was authored as `Cursor Agent <agent@cursor.ai>` (existing identity), not invented.
- If the credential helper blocks with a GUI dialog, the push will hang silently. Watch for `git.exe` and `git-credential-manager-*.exe` processes in Task Manager; if they linger with no output, kill them before retrying.

## Diagnostic checklist (in order)

1. Confirm the error string mentions `schannel` and `missing close_notify`. If you only see `authentication failed` or `403`, this document does not apply — it is a credential issue.
2. Check for VPN / corporate proxy / Transparent TLS-inspection middleboxes. If any are active, prefer this fix or the SSH path. This machine had no obvious proxy configured but still hit it.
3. Make sure no orphan git processes are left from a prior failed push (`Get-Process git`); they may hold the credential dialog open.
4. Try the OpenSSL workaround (single command above). Expected runtime: 5–15 s for a small repo; if it hangs past 60 s, kill the git tree and retry once.
5. If still failing, switch the upstream to SSH: `git remote set-url origin git@github.com:<owner>/<repo>.git`, then push with the existing SSH key. This is a one-time URL change in `.git/config` which is not the same as mutating the global identity config the rules forbid.

## Related

- `memory/facts/windows-shell-encode-gotchas.md` covers a different failure mode: PowerShell harness re-encoding file content to UTF-16. Same environment, different layer.
