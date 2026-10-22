# Strata Turbo: the easiest install on Windows

Strata Turbo runs a smart chat (the Cyber-Tiel-Coder language model) right on your own PC. This guide is for people
who do not want to deal with settings: you download one file and run it, and the installer does everything else by
itself. It asks no questions.

> Русская версия: [EASY_INSTALL.ru.md](EASY_INSTALL.ru.md). Every other way to install: [INSTALL.md](INSTALL.md).

## What you need

- **Windows 10 or 11.**
- **An NVIDIA GeForce RTX 20 series graphics card or newer**: RTX 2060, 3060, 4060, 5070 and so on. 12 GB of graphics
  memory or more is best: with less, Strata Turbo runs, but slower.
  To see your card: press Ctrl+Shift+Esc, open "Performance" and pick "GPU". Its name is at the top right.
- **32 GB of memory (RAM) or more.** Where to look: Start → Settings → System → About, the line "Installed RAM".
- **About 21 GB of free disk space.** When drive C: has too little, the installer picks another drive that has
  enough, and says so.
- **The internet.** About 18 GB is downloaded.
- **NVIDIA graphics driver 580 or newer.** The installer checks it and, if it is too old, says how to update it.

The installer checks all of this **before** it downloads anything. If something is missing, it stops and says in one
sentence what is wrong and what to do.

## How long it takes

| What | How long |
| --- | --- |
| Checking the PC | a few seconds |
| Downloading the app (about 520 MB) | 1-5 minutes, depending on the internet |
| Installing the app and its components | 1-5 minutes (under a minute on the test PC) |
| Downloading the model (17 GB) | depends on the internet speed, see below |
| The first start | 1-3 minutes |

The model is 18.1 billion bytes (17 GB in File Explorer). By arithmetic, it takes about 50 minutes at 50 Mbit/s,
about 25 minutes at 100 Mbit/s and about 8 minutes at 300 Mbit/s. The installer measures your speed and shows how
much time is left.

## Step by step

### Step 1. Download the installer

Open the latest release: https://github.com/Asofwar/Strata-Turbo/releases/latest

Scroll down to **Assets** and click **`Strata-Turbo-Install.cmd`**. It is a small file of a few kilobytes.

Your browser may warn that such files are not commonly downloaded. It says this about every `.cmd` file.

- **Microsoft Edge** says "Strata-Turbo-Install.cmd isn't commonly downloaded...". Point at that line, click
  "**...**" → "**Keep**". If one more window appears, click "**Show more**" → "**Keep anyway**".
- **Google Chrome** may say "Unverified download blocked". Click that line, then "**Download unverified file**".
- Often the browser asks nothing and saves the file to your Downloads folder.

### Step 2. Run it

Open your **Downloads** folder and double-click **`Strata-Turbo-Install.cmd`**.

Windows may ask again. Which window you get depends on Windows' settings:

- "**Open File - Security Warning**", with "The publisher could not be verified". Click "**Run**".
- A blue "**Windows protected your PC**" window. Click "**More info**", then "**Run anyway**".
- A message that Windows **blocked** the file, with no Run button (that is Smart App Control). Close it. Right-click
  the file → "**Properties**". At the bottom of the General tab tick "**Unblock**" and click "**OK**". Then
  double-click the file again.

Windows asks this about any file from the internet that has no publisher's digital signature. The Strata Turbo
installer is not signed.

### Step 3. Wait

A black installer window opens. You do not need to click anything. The window shows what is happening:

```
Step 1 of 5. Checking this PC
   + Graphics card: NVIDIA GeForce RTX 5080, 16 GB of graphics memory, driver 617.42
   + Memory (RAM): 48 GB
   + Disk space: enough (about 21 GB needed), install folder C:\Users\...\AppData\Local\Strata-Turbo
   + Internet: works

Step 2 of 5. Downloading Strata Turbo 1.2.0
Step 3 of 5. Installing the app and its components
Step 4 of 5. Downloading the model
   [##########--------------]  42%  7.1 / 16.9 GB  about 14 min left
Step 5 of 5. Creating the icons and starting
```

The longest step is the model download (step 4). The bar shows how much is downloaded and about how long is left.
You can leave the PC alone.

If the window was closed by accident or the internet dropped, run `Strata-Turbo-Install.cmd` again: the download
goes on from where it stopped.

### Step 4. Done

At the end the window says "**Done! Strata Turbo is installed.**", and a **Strata Turbo** icon appears on the
desktop. Right after that, Strata Turbo starts in the same window. In 1-3 minutes the chat opens in your browser by
itself. While the model loads, the PC can be slow: that is normal.

## Using the chat

The chat opens in your browser by itself. Its address is in the Strata Turbo window, on the line "The chat" (usually
http://127.0.0.1:8080/). It is a page on your own PC, not a website.

1. At the bottom there is a box saying "**Ask anything…**". Type your question there.
2. Press **Enter** or the green arrow button to the right of the box. Shift+Enter starts a new line in a message.
3. The model thinks first, then writes the answer. Above the answer a line "**Thought for … s**" appears: click it to
   see its reasoning.
4. The "**New chat**" icon at the bottom left, under the box, starts a new conversation. Point at the icons to see
   their names.
5. The state is at the top right: "**Idle**" means the model is free and waiting for a question.

While you use the chat, keep the black **Strata Turbo** window open: closing it stops the model.

## Starting Strata Turbo later

- Double-click the **Strata Turbo** icon on the desktop (or Start → Strata Turbo). The Strata Turbo window opens, and
  in 1-3 minutes the chat opens in your browser.
- If Strata Turbo is already running, the icon just opens the chat.
- **To stop it**: close the Strata Turbo window. Or Start → the "Strata Turbo" folder → "**Stop Strata Turbo**".

While Strata Turbo runs, it uses the graphics card and a lot of memory, so games and heavy programs run worse. Stop it
when you do not need the chat.

## If something goes wrong

Every error ends with one sentence saying what to do, and a line "Details are in: …" with the log file's path. Usually
it is `install.log` in the install folder (`C:\Users\<name>\AppData\Local\Strata-Turbo\install.log`); when setup
stopped at its first step, `strata-turbo-install.log` in the temporary folder. When you ask for help, attach this file.

1. **Windows will not run the file, or the window closes at once.** Right-click `Strata-Turbo-Install.cmd` →
   Properties → tick "Unblock" → OK. Run the file again (step 2).
2. **"The graphics driver is too old".** Open the **NVIDIA App** → Drivers → Download. Without it, download the driver
   from https://www.nvidia.com/en-us/drivers/ (choose your card). Then restart the PC and run the installer again.
3. **"Not enough free space".** Empty the Recycle Bin, delete files you do not need or run "Disk Cleanup" (find it
   from Start). About 21 GB of free space is needed. Then run the installer again.
4. **"No internet connection", or the download stopped.** Check that the internet works (open any website). Run the
   installer again: what is already downloaded is not downloaded again.
5. **The chat did not open, or the window says "Strata Turbo stopped with an error".** Wait 3 minutes: the first start
   after turning the PC on can be slow. Try opening the chat's address from the Strata Turbo window (usually
   http://127.0.0.1:8080/) in your browser yourself. If that does not
   help, restart the PC and start Strata Turbo with the desktop icon. Close games and other programs that use the
   graphics card.

If the installer says that **no graphics card was found or it is too old**, or that there is **not enough memory**,
Strata Turbo will not run on this PC: it needs an NVIDIA RTX 20 series card or newer and 32 GB of RAM.

## Updating

Run `Strata-Turbo-Install.cmd` again (the same file or a new download: it always installs the newest version). If
Strata Turbo is running, the installer stops it. The downloaded model stays and is not downloaded again. The new
version gets the recommended settings. If there is no new version, the installer says the newest one is already
downloaded and just starts Strata Turbo.

## Removing it

Start → the "Strata Turbo" folder → "**Uninstall Strata Turbo**". Or Settings → Apps → Installed apps (Windows 10:
Apps & features) → Strata Turbo → Uninstall.

The window asks two questions:

1. "Remove Strata Turbo from this PC?" Type **y** and press Enter.
2. "Delete the downloaded model too?" Type **y** to free 17 GB. Type **n** (or just press Enter) if you may install
   Strata Turbo again: then the model does not need to be downloaded again.

The app's folder, the desktop icon, the Start menu folder and the line in the Apps list are removed.

## For experienced users

- Where it goes: `%LOCALAPPDATA%\Strata-Turbo\<version>`. A user name with a space or non-English letters gets
  `C:\Strata-Turbo` instead; when drive C: has too little space, `<drive>:\Strata-Turbo` on the drive with the most
  free space. The model goes to `Strata-data` beside it. If the PC already has Strata with a model folder, the installer
  uses that one. Older versions stay in the install folder (about 1.6 GB each).
- What it runs: `START-HERE.bat --setup --family cyber-tiel --yes --no-start` (plus `--draft-vocab cyrillic` when
  Windows is in Russian), then `run-cybertiel-ud-iq4_xs.bat`. The icons run `Strata-Turbo.ps1 start | stop | uninstall`
  in the install folder.
- The options (environment variables `STRATA_HOME`, `STRATA_VERSION`, `STRATA_DATA_DIR`, `STRATA_SETUP_ARGS`,
  `STRATA_NO_START`, `STRATA_LANG` and more) are listed at the top of `packaging/fork/easy-install.ps1`.
- Measured (RTX 5080 16 GB, i9-14900K, 48 GB, NVMe, the model already on the disk): a fresh install without the model
  download took 54 s, an update to a new version 31 s, and the chat opened about 15 s after the start (the model file
  was in Windows' file cache).
- The one-liner `irm https://github.com/Asofwar/Strata-Turbo/releases/latest/download/install.ps1 | iex` works as
  before and asks for the model. Every way: [INSTALL.md](INSTALL.md).
