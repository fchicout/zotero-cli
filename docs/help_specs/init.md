# DOC-SPEC: init

## 1. Classification
- **Level:** 🟡 MODIFICATION (Configuration Initialization)
- **Target Audience:** New User / SysAdmin

## 2. Logic Flow (Visual Synthesis)
```mermaid
graph TD
    A["Start Init"] --> B{"Existing Config?"}
    B -- "Yes" --> C{"--force Flag?"}
    B -- "No" --> D["Start Wizard"]
    C -- "No" --> E[""End: Abort (Safety")"]
    C -- "Yes" --> D
    D --> F["Collect: API Key, User/Group ID"]
    F --> G[""Collect: Paths (Storage, Cache")"]
    G --> H["Validate Credentials via API"]
    H --> I["Generate config.toml"]
    I --> J["End: Initialization Success"]
```

## 3. Synopsis
Launches an interactive setup wizard to configure the Zotero CLI, establishing connection credentials and local storage paths.

## 4. Description (Instructional Architecture)
The `init` command is the gateway to using `zotero-cli`. It simplifies the configuration process by guiding the user through a series of prompts. 

The command identifies your Zotero profile (Personal or Group) and establishes an authenticated connection to the Zotero API. It also defines where your PDF attachments should be stored and where the local database cache will be maintained. The result of this process is a `config.toml` file, which is used by all other commands in the library. 

## 5. Parameter Matrix
| Flag | Type | Description | Ergonomic Note |
| :--- | :--- | :--- | :--- |
| `--force` | Flag | Overwrites any existing `config.toml` file. | Required if re-configuring. |

## 6. Scenario-Based Examples (Cognitive Anchors)
### Scenario: First-time setup of the CLI
**Problem:** I've just installed the `zotero-cli` and I need to connect it to my Zotero account.
**Action:** `zotero-cli init`
**Result:** The CLI asks for my API key and Library ID, then creates the configuration file.

## 7. Cognitive Safeguards
- **Common Failure Modes:** Providing an incorrect API key or ID during the wizard. The CLI will attempt to validate these via a heartbeat request to the API. 
- **Safety Tips:** Keep your API key private. The `init` command stores it in a plain-text `config.toml` file by default, so ensure your configuration directory has restricted access permissions.
