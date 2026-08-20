# Stenotyping Practice

A lightweight desktop practice app for learning and improving **stenotype with Plover**.

The app gives you words or continuous text to write, displays the corresponding steno strokes from a Plover dictionary, and tracks basic practice statistics such as WPM and streaks.

## Features

* **Random word practice** from a configurable word bank
* **Sequential text practice** for sentences, quotes, or longer passages
* Displays **steno stroke hints** using a Plover dictionary
* Supports standard Plover `stroke -> translation` JSON dictionaries
* Live **WPM tracking**
* Correct attempt and streak tracking
* Automatic advancement after correctly writing a word
* Instant visual feedback while typing
* Remembers previously loaded word bank and dictionary files
* Lightweight native GUI built with Python and Tkinter

## How It Works

Stenotyping Practice does not replace Plover or communicate with it directly.

Instead, Plover runs normally and translates stenotype chords into keyboard input. The application receives that translated text just like any other program and checks it against the current target.

For example:

```text
Target: message
Hint:   PHEPBLG

Steno keyboard
     ↓
   Plover
     ↓
"message"
     ↓
Practice App ✓
```

This keeps the application simple and allows it to work with your existing Plover setup and theory.

## Practice Modes

### Word Bank

Loads words or phrases from a `.txt` file and presents them in random order.

The included `words.txt` can be used as a starting word bank.

```text
because
between
different
another
something
```

Empty lines and lines beginning with `#` are ignored.

### Source Text

Paste any text into the source box and select **Use Source Text (Sequential)**.

The app breaks the text into tokens and presents them in order, allowing you to practice continuous prose rather than isolated vocabulary.

This is useful for practicing:

* quotes
* articles
* song lyrics
* class notes
* common sentences
* arbitrary text you want to become comfortable writing

## Dictionary Support

The app can load Plover-compatible JSON dictionaries.

Standard Plover dictionaries use strokes as keys:

```json
{
    "PHEPBLG": "message",
    "KREL/HRER": "cellular"
}
```

Translation-first dictionaries are also supported:

```json
{
    "message": ["PHEPBLG"],
    "cellular": "KREL/HRER"
}
```

Internally, both formats are normalized so the application can look up strokes for the current practice word.

The repository includes `main.json`, which can be loaded directly as a dictionary.

## Session Statistics

The application tracks:

| Statistic              | Description                                                 |
| ---------------------- | ----------------------------------------------------------- |
| **WPM**                | Typing speed using the standard 5-character word convention |
| **Accuracy**           | Percentage of counted attempts completed correctly          |
| **Correct / Attempts** | Number of successful attempts                               |
| **Streak**             | Current and best consecutive correct count                  |
| **Time**               | Current session duration                                    |

WPM is calculated as:

```text
(characters typed / 5) / minutes
```

## Installation

Requires **Python 3.10+**.

Clone the repository:

```bash
git clone https://github.com/bsig1/stenotyping.git
cd stenotyping
```

Then run:

```bash
python stenotype.py
```

### Tkinter

Tkinter is included with many Python installations.

On some Linux distributions it must be installed separately.

For example, on Arch Linux:

```bash
sudo pacman -S tk
```

### Pillow

[Pillow](https://pypi.org/project/pillow/) is optionally used to load the application icon:

```bash
pip install pillow
```

The practice application will still run if Pillow is unavailable.

## Getting Started

1. Start and configure **Plover** with your stenotype keyboard.
2. Run `stenotype.py`.
3. Click **Load Word Bank** and select `words.txt`.
4. Click **Load Dictionary JSON** and select `main.json`.
5. Start writing the displayed words with Plover.

Once loaded, the selected file paths are stored in:

```text
~/.config/plover_practice/config.json
```

and automatically restored the next time the application starts.

## Controls

* **Enter** — submit a completed word
* **Escape** — clear the current input
* **Next** — skip the current target
* **Reset Session** — reset statistics
* **Restart Quote** — restart sequential source-text practice

Correct words automatically advance to the next target.

## Repository Structure

```text
stenotyping/
├── stenotype.py    # Application and GUI
├── words.txt       # Practice word bank
├── main.json       # Plover dictionary
├── icon.png        # Application icon
└── icon.jfif
```

## Why?

Steno practice often involves either learning theory or writing large amounts of predefined material. I wanted a smaller tool for quickly drilling arbitrary vocabulary while still having the relevant Plover strokes visible.

The goal is intentionally simple:

**open it, load a dictionary, and practice.**

## Built With

**Python · Tkinter · Plover**
