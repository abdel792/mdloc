# mdloc

**mdloc** stands for **Markdown Localisation**.

mdloc is a lightweight CLI tool that converts Markdown files to XLIFF 2.x  
using the standard skeleton mechanism defined in the XLIFF specification.

The skeleton preserves the original Markdown structure while translatable  
segments are extracted into translation units.

---

## Features

- Convert Markdown → XLIFF 2.0 / 2.1  
- The implementation follows common industry practices used by modern localization platforms  
- UUID-based translation units  
- Reconstruct translated Markdown from XLIFF  
- Fully local workflow  
- BOM-safe (UTF-8 clean output)  
- Simple CLI interface  

---

## How It Works

### Extraction (Markdown → XLIFF)

- Markdown text is parsed  
- Translatable text segments are extracted  
- Each segment receives a unique ID  
- The original Markdown structure is preserved in a `<skeleton>` element  
- Extracted text becomes `<unit>` entries in XLIFF  
- The generated `.xliff` file is created in the same directory as the source Markdown file  

### Reconstruction (XLIFF → Markdown)

- The skeleton is loaded  
- Each `$(ID:xxxx)` placeholder is replaced by the translated text  
- A reconstructed Markdown file is generated  
- The output file is created with the suffix `.translated.md`  

---

# Installation

## Requirements

- Python 3.9+  
- pip  

---

## 1. Clone the Repository

```bash
git clone https://github.com/abdel792/mdloc.git
cd mdloc
```

---

## 2. Install the Package (Editable Mode)

From the root directory of the repository, run:

```bash
python -m pip install -e .
```

This installs the package in editable (development) mode, allowing you to modify the source code without reinstalling the package.

---

# Usage

After installation, you can use the CLI from **any directory**.

Navigate (using Terminal or PowerShell) to the folder containing the file you want to process.

---

## Extract Markdown to XLIFF

If the current directory contains a Markdown file you want to convert:

```bash
python -m mdloc.cli extract filename.md
```

This command:

- Reads the Markdown file  
- Extracts translatable segments  
- Generates an XLIFF file in the same directory  

The output file will have the same base name with the `.xliff` extension:

```
filename.xliff
```

---

## Reconstruct Markdown from XLIFF

If the current directory contains a translated XLIFF file:

```bash
python -m mdloc.cli reconstruct filename.xliff
```

This command:

- Loads the skeleton and translations  
- Replaces each `$(ID:xxxx)` placeholder with its corresponding translated text  
- Generates a reconstructed Markdown file  

The output file will be created as:

```
filename.translated.md
```

---

# Uninstallation

To uninstall the package:

```bash
python -m pip uninstall mdloc
```

---

# Example Workflow

1. Write your Markdown file:

   ```
   document.md
   ```

2. Extract translatable content:

   ```bash
   python -m mdloc.cli extract document.md
   ```

3. Send the generated `document.xliff` to translators  
4. Receive the translated XLIFF file  
5. Reconstruct the translated Markdown:

   ```bash
   python -m mdloc.cli reconstruct document.xliff
   ```

6. The final localized file will be:

   ```
   document.translated.md
   ```

---

mdloc keeps your localization workflow simple, transparent, and fully local.