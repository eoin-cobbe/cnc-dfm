# cnc-dfm

## What this project is
`cnc-dfm` is a command-line Design for Manufacturing checker for CNC parts. Give it a STEP file and it analyzes geometry against five core machining rules, then returns a readable pass/fail report with a short explanation for each rule.

## Install (one time)
```bash
git clone https://github.com/eoin-cobbe/cnc-dfm.git
cd cnc-dfm
./scripts/install.sh
```

## Use it (2 steps, every time)

1. Open terminal and go to the folder that contains your STEP file.
```bash
cd /path/to/your/part/folder
```

2. Run the checker.
```bash
run
```

`run` opens an in-terminal STEP picker.  
If you already know the file path, you can run directly:
`run /path/to/part.step`.

If you did not add global `run`, use:
`/path/to/cnc-dfm/run /path/to/part.step`
