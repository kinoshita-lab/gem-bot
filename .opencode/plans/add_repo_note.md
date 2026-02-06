# Plan: Add Repository Note

## Goal
Add a note to `README.md` and `README.ja.md` stating that the official repository is `https://git.kinoshita-lab.org/kazbo/gem-bot` and others are mirrors.

## Steps

### 1. Update `README.md` (English)
Insert the following note after the description (around line 4):
```markdown
> **Note:** The official repository is hosted at [https://git.kinoshita-lab.org/kazbo/gem-bot](https://git.kinoshita-lab.org/kazbo/gem-bot). Other locations are mirrors.
```

### 2. Update `README.ja.md` (Japanese)
Insert the following note after the description (around line 4):
```markdown
> **注意:** 最新のリポジトリは [https://git.kinoshita-lab.org/kazbo/gem-bot](https://git.kinoshita-lab.org/kazbo/gem-bot) で公開されています。他はミラーです。
```

### 3. Commit and Push
Commit with message: `docs: add official repository location note`
