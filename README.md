Of course. Here is the complete `README.md` file, updated with your name, email, and a placeholder for your GitHub repository link.

I've added a new "Author" section and made the link in the "Contributing" section explicit.

**Action Required:** Remember to replace the placeholder `https://github.com/your-username/pyp6` with the actual URL to your GitHub repository once you create it.

---

### `README.md`

```markdown
# PyP6: Python for Primavera P6

[![PyPI version](https://badge.fury.io/py/pyp6.svg)](https://badge.fury.io/py/pyp6)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PyP6** is a command-line toolkit designed to streamline and automate workflows for Oracle Primavera P6 by directly interacting with its SQLite database. It allows project managers, planners, and developers to programmatically add and manage project data like OBS, WBS, Activities, and Relationships using simple CSV files.

This package is ideal for:
-   Bulk-loading data into new projects.
-   Automating the creation of standardized project structures.
-   Integrating P6 with other data sources and systems.
-   Reducing manual data entry and minimizing errors.

## Features

-   **Modular Scripts**: Separate, focused command-line tools for each data type.
-   **Simple Configuration**: A one-time setup command creates an easy-to-edit configuration file.
-   **CSV-Driven**: Uses standard, easy-to-create CSV files as the data source.
-   **Intelligent Linking**: Automatically handles relationships between new and existing activities.
-   **Robust and Safe**: Uses database transactions to ensure that imports are all-or-nothing, preventing partial, corrupted data.

## Author

*   **Sanjeev Bashyal**
*   Contact: [sanjeev.bashyal01@gmail.com](mailto:sanjeev.bashyal01@gmail.com)

---

## Installation

PyP6 requires Python 3.8 or higher. You can install it directly from PyPI using pip.

```bash
pip install pyp6
```

---

## Getting Started: A 3-Step Guide

Using PyP6 is a simple, three-step process.

### Step 1: Initialize Your Configuration (One-Time Setup)

Before using any of the import scripts, you must first initialize PyP6. Open your terminal or command prompt and run:

```bash
pyp6-init
```

This command will create a new configuration file at a standard location in your user's home directory (e.g., `C:\Users\YourName\.pyp6\config.json` on Windows or `~/.pyp6/config.json` on macOS/Linux).

The output will look like this:

```
No configuration file found. Creating a new template at: C:\Users\YourName\.pyp6\config.json

SUCCESS: A new configuration file has been created.

IMPORTANT: You must now edit this file with your actual paths.
  -> Edit file: C:\Users\YourName\.pyp6\config.json

File contents:
-------------
{
    "target_project_id": "UTHP",
    "hours_per_day": 8.0,
    "user_name": "PyP6_Script",
    "database_path": "C:\\path\\to\\your\\database.db",
    "data_folder_path": "C:\\path\\to\\your\\Data"
}
-------------
```

**You must now open this `config.json` file and edit the placeholder paths:**

1.  `database_path`: Change this to the full path of your P6 SQLite (`.db`) file.
2.  `data_folder_path`: Change this to the full path of the folder where you will store your CSV input files.
3.  You can also change the default `target_project_id`, `hours_per_day`, and `user_name` to match your environment.

### Step 2: Prepare Your CSV Data Files

In the data folder you specified in `config.json`, create the CSV files for the data you wish to import. The structure for each file is detailed below.

### Step 3: Run the Import Scripts

Once your configuration is set and your CSV files are ready, you can run the import scripts from your terminal. The order matters for hierarchical data.

A typical workflow would be:

```bash
# 1. Import the Organizational Breakdown Structure
pyp6-obs

# 2. Import the Work Breakdown Structure
pyp6-wbs

# 3. Import Activities and their Relationships
pyp6-activities
```

**Important**: After importing activities or relationships, you must open the project in Primavera P6 and **reschedule it (press F9)** for the changes to be fully calculated and reflected in the Gantt chart.

---

## CSV File Formats

All CSV files should be placed in the `data_folder_path` defined in your `config.json`.

### 1. OBS (`obs.csv`)

Used by the `pyp6-obs` command. Defines the organizational hierarchy.

| OBS_Name      | Parent_OBS_Name |
|---------------|-----------------|
| UTHP          |                 |
| PMC           | UTHP            |
| Contractor    | UTHP            |
| Engineering   | PMC             |

*   **`OBS_Name`**: The name of the OBS element.
*   **`Parent_OBS_Name`**: The name of the parent OBS element. Leave blank for top-level elements.

### 2. WBS (`wbs.csv`)

Used by the `pyp6-wbs` command. Defines the project's work breakdown structure.

| WBS Short Name | WBS Name                      | Parent WBS Name        |
|----------------|-------------------------------|------------------------|
| UTHP.1         | Mobilization                  |                        |
| UTHP.3         | Construction Works            |                        |
| UTHP.3.1       | Headrace Tunnel & Surge Shaft | Construction Works     |

*   **`WBS Short Name`**: The unique code or identifier for the WBS element.
*   **`WBS Name`**: The descriptive name of the WBS element.
*   **`Parent WBS Name`**: The name of the parent WBS element. Leave blank for elements directly under the project root. **Parent rows must appear before their children in the CSV.**

### 3. Activities (`activities.csv`)

Used by the `pyp6-activities` command. Defines activities, their placement in the WBS, and their logical relationships.

| Activity_ID | Activity_Name                            | Duration_Days | WBS_Name           | Predecessors               |
|-------------|------------------------------------------|---------------|--------------------|----------------------------|
| A1000       | Site Mobilization                        | 20            | Mobilization       |                            |
| A1010       | Foundation Works                         | 30            | Construction Works | A1000                      |
| A1020       | Start Steel Erection                     | 15            | Construction Works | A1010[SS+5d]               |
| A1030       | Final Inspection                         | 5             | Mobilization       | A1010[FS], A1020[FF-2d]    |

*   **`Activity_ID`**: The unique code for the activity.
*   **`Activity_Name`**: The descriptive name.
*   **`Duration_Days`**: The duration in days (will be converted to hours based on your config).
*   **`WBS_Name`**: The name of the WBS element to place this activity under. Leave blank to place it under the project root.
*   **`Predecessors`**: A comma-separated list of predecessor activities. The format is `ActivityID[Type+Lag]`.
    *   **Type**: `FS`, `SS`, `FF`, `SF`. Defaults to `FS` if omitted.
    *   **Lag**: A number followed by `d` (days) or `h` (hours). E.g., `+5d`, `-10h`. Defaults to `0` if omitted.

### 4. Roles (`roles.csv`)

Used by the `pyp6-roles` command. Defines the global roles hierarchy.

| Role_Name      | Role_Short_Name | Parent_Role_Name |
|----------------|-----------------|------------------|
| Engineering    | ENG             |                  |
| Civil Engineer | CIVIL           | Engineering      |
| Project Mgmt   | PM              |                  |

---

## Contributing

Contributions are welcome! If you have ideas for new features, improvements, or have found a bug, please feel free to open an issue or submit a pull request on the project's GitHub repository.

**[https://github.com/SanjeevBashyal/PyP6](https://github.com/SanjeevBashyal/PyP6)**
```