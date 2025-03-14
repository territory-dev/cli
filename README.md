Uploading sources with the territory.dev CLI client
===================================================

Watch a video walkthrough:

[![YouTube video showing an example of using the client](https://img.youtube.com/vi/2gYkxGcLPoM/1.jpg)](https://www.youtube.com/watch?v=2gYkxGcLPoM)

## 1. Prepare your repository

### For C/C++ Projects
Clone your repository and generate `compile_commands.json`. See examples of how this can be generated
[here](https://github.com/territory-dev/builds?tab=readme-ov-file#how-do-i-generate-compile_commandsjson).

### For Go Projects
Clone your repository and ensure your Go module is properly initialized:

```bash
go mod download
```

### For Python Projects
If you created a virtualenv for your project, we recommend you install and run `territory` with
it activated.

## 2. Add a new repo in the territory.dev interface

Go to settings,

![](./doc/Screenshot%202024-08-22%20at%2008.54.51.png)

find the "[Add](https://app.territory.dev/repos/new)" button under
Repositories,

![](./doc/Screenshot%202024-08-22%20at%2008.56.12.png)

enter repository details, choose the "Uploaded" option, and select the appropriate language (C/C++ or Go),

![](./doc/Screenshot%202024-08-22%20at%2008.57.26.png)

create the new repository by clicking "Save".

## 3. Install the client

Install with pip within a Python virtualenv:

```
pip install territory
```

## 4. Run the upload

### For C/C++ Projects
In the directory containing `compile_commands.json` run:

```bash
territory upload --repo-id $YOUR_REPOSITORY_ID -l c
```

### For Go and Python Projects
In your git repository run:

```bash
# Go:
territory upload --repo-id $YOUR_REPOSITORY_ID -l go

# Python:
territory upload --repo-id $YOUR_REPOSITORY_ID -l python
```
We will scan the repo for modules, package parse results and send the code
for indexing.

The specific command containing the repository ID can be found in repository
settings under "Recent builds".

First time you use the client, we will open the web browser and you will be
asked to authenticate the client in the web app.

Once the upload finishes, indexing will start.


Non-interactive authentication
==============================

In case you need to run the upload in an environment where the browser
authentication flow is not suitable (e.g. a CI build), you can provide
the necessary token manually.

1.  In "Settings" go to to
    [Upload tokens](https://app.territory.dev/upload-tokens).
2.  Create a new token and save its text to a file.
3.  Point the CLI to the file by adding the `--upload-token-path`, e.g.:
    ```
    territory upload \
        --upload-token-path /path/to/token \
        --repo-id $YOUR_REPOSITORY_ID
    ```
