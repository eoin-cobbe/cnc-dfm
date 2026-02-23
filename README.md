# cnc-dfm

## What this project is
`cnc-dfm` is a command-line Design for Manufacturing checker for CNC parts. Give it a STEP file and it analyzes geometry against five core machining rules, then returns a readable pass/fail report with a short explanation for each rule.

## Install
```bash
brew install --cask miniforge
git clone <repo-url>
cd cnc-dfm
```

## Start a terminal session
```bash
./run /path/to/part.step
```
