Uploading sources with the territory.dev CLI client
===================================================

Watch a video walkthrough:

[![YouTube video showing an example of using the client](https://img.youtube.com/vi/2gYkxGcLPoM/1.jpg)](https://www.youtube.com/watch?v=2gYkxGcLPoM)

## 1. Clone a git repository and generate `compile_commands.json`

See examples of how `compile_commands.json` can be generated
[here](https://github.com/territory-dev/builds?tab=readme-ov-file#how-do-i-generate-compile_commandsjson).

## 2. Add a new repo in the territory.dev interface

Go to settings,

![](./doc/Screenshot%202024-08-22%20at%2008.54.51.png)

find the "[Add](https://app.territory.dev/repos/new)" button under
Repositories,

![](./doc/Screenshot%202024-08-22%20at%2008.56.12.png)

enter repository details and choose the "Uploaded" option,

![](./doc/Screenshot%202024-08-22%20at%2008.57.26.png)

create the new repository by clicking "Save".

## 3. Install the client

Install with pip within a Python virtualenv:

```
pip install territory
```

## 4. Run the upload

In the directory containing `compile_commands.json` run

```
territory upload --repo-id $YOUR_REPOSITORY_ID
```

The specific command containing the repository ID can be found in repository
settings under "Recent builds".

First time you use the client, we will open the web brower and you will be
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
