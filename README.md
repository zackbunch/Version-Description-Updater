# Ansible POM Updater

This project provides a set of Ansible roles and a playbook to enforce and update versions of dependencies, plugins, and the project itself within a Maven `pom.xml` file.

## Requirements

*   Ansible
*   The `community.general` collection must be installed:
    ```bash
    ansible-galaxy collection install community.general
    ```

## Configuration

This project uses two JSON files to define the desired versions:

*   `applications.json`: A JSON object mapping `artifactId` to a desired `version` for your projects.
*   `dependencies.json`: A JSON object mapping `artifactId` to a desired `version` for both dependencies and plugins.

## Usage

The main entry point is the `playbooks/enforce_pom.yml` playbook. This playbook will:

1.  Read a specified `pom.xml` file.
2.  Read the `applications.json` and `dependencies.json` files.
3.  Update the project version, dependency versions, and plugin versions in the `pom.xml` file to match the versions specified in the JSON files.

To run the playbook, you need to set the `pom_file` environment variable to the path of the `pom.xml` you want to modify.

**Example:**

```bash
export pom_file=$(pwd)/fixtures/sample_proj/pom.xml
ansible-playbook playbooks/enforce_pom.yml
```

### Roles

This project includes the following roles:

*   **`pom_reader`**: Reads a `pom.xml` file and extracts information about the project, dependencies, and plugins into Ansible facts.
*   **`pom_project_updater`**: Updates the `<version>` of the project in the `pom.xml` based on the versions defined in `applications.json`.
*   **`pom_deps_updater`**: Updates the versions of dependencies in the `pom.xml` based on the versions defined in `dependencies.json`.
*   **`pom_plugin_updater`**: Updates the versions of plugins in the `pom.xml` based on the versions defined in `dependencies.json`.

By default, the playbook runs the `pom_reader` and `pom_plugin_updater` roles. You can edit `playbooks/enforce_pom.yml` to enable the other updater roles.
