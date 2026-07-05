# Release notes

Per-version bilingual (English / 中文) release notes for
`xhs-saas-console`. These files are the source-of-truth body that gets
pasted into the GitHub Release "Describe this release" field at publish
time.

## Layout

```
installer/docs/RELEASE_NOTES/
  v0.6.0.md
  v0.6.1.md
  ...
```

## How to use

1. Copy the template that matches your milestone (e.g. `v0.6.1.md`).
2. Fill in the highlights and quick-start sections for your release.
3. Keep English first, Chinese second, separated by an empty line.
4. At release time, paste the file's contents into the GitHub Release
   editor body. Or, from the CLI:

   ```powershell
   gh release create v0.6.1 `
     --title "v0.6.1 - <short summary>" `
     --notes-file installer/docs/RELEASE_NOTES/v0.6.1.md `
     dist\xhs-saas-console-0.6.1.msi
   ```

## Style

- Plain Markdown. GitHub renders it directly.
- Use the same icon set on each release so the visual rhythm is stable.
- Asset hashes go under a `Checksums` table, not inline.
- Known issues go under `Known issues`, not in the highlights.
- Always link to `CHANGELOG.md` for the full history.