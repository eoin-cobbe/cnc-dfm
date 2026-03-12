<div align="center">
<pre>
 ######   ##    ##   ######     ######    ########  ##     ##
##    ##  ###   ##  ##    ##    ##   ##   ##        ###   ###
##        ####  ##  ##          ##    ##  ##        #### ####
##        ## ## ##  ##          ##    ##  ######    ## ### ##
##        ##  ####  ##          ##    ##  ##        ##  #  ##
##    ##  ##   ###  ##    ##    ##   ##   ##        ##     ##
 ######   ##    ##   ######     ######    ##        ##     ##
</pre>
</div>

# cnc-dfm

`cnc-dfm` checks CNC STEP files against core manufacturability rules.

It has two ways to use it:

- `Terminal`: fast CLI workflow
- `macOS App`: native viewer and analysis UI

## Terminal Install

Prerequisites:

- Install Miniforge, Conda, or Mamba first.
- The installer then creates this repo's own `.conda-env` and installs Python and `pythonocc-core` into it.

macOS / Linux:

```bash
git clone https://github.com/eoin-cobbe/cnc-dfm.git
cd cnc-dfm
./scripts/install.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/eoin-cobbe/cnc-dfm.git
cd cnc-dfm
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

## Terminal

One-time setup:

```bash
run config
```

Run a part:

```bash
cd /path/to/your/part/folder
run
```

Or run directly on a file:

```bash
run /path/to/part.step
```

## macOS App

Build the macOS dist:

```bash
cd apps/macos/CNCDFMApp
./Scripts/build-local-app.sh
```

A macOS `.app` dist is then available at `apps/macos/CNCDFMApp/dist/CNCDFMApp.app`.

Open it:

```bash
open dist/CNCDFMApp.app
```

## Docs

- CLI commands: [docs/CLI_API.md](docs/CLI_API.md)
- macOS app notes: [apps/macos/CNCDFMApp/README.md](apps/macos/CNCDFMApp/README.md)
